# 📊 PHASE 4 — EXECUTION VALIDATION

## 1. System Execution Flow (Step-by-Step)

### A. Backend Startup (`uvicorn app.main:app --port 8010`)

```
1. Module-level code runs:
   ├── config.py:get_settings()        → Load .env via pydantic-settings
   ├── config.py:configure_logging()   → Set log format + level
   └── main.py:app = FastAPI(...)      → Create app, register middleware + routes

2. Lifespan startup (main.py:lifespan):
   ├── [2a] Validate config             → Fail fast if no DATABASE_URL
   ├── [2b] Create SQLAlchemy engine    → PostgreSQL (QueuePool) or SQLite (StaticPool)
   ├── [2c] Create SessionLocal factory → sessionmaker bound to engine
   ├── [2d] Base.metadata.create_all()  → Create/verify all ORM tables
   │         Tables: stations, sections, trains, train_schedules,
   │                 train_states, optimization_logs,
   │                 historical_operational_data, kpi_metrics, manual_overrides
   ├── [2e] Verify DB connection        → SELECT 1 + inspect table names
   ├── [2f] Setup DI overrides          → Replace routes.get_db_session with real sessions
   └── [2g] Initialize PredictionService → Load/create ML models (optional, non-blocking)

3. Server ready at http://localhost:8010
   ├── API docs:   http://localhost:8010/api/docs
   ├── Health:     http://localhost:8010/api/v1/health
   └── Readiness:  http://localhost:8010/health/ready
```

### B. Frontend Startup (`npm run dev` → Vite on port 3001)

```
1. main.tsx renders <App />
2. App wraps everything in <LiveDataProvider>
3. LiveDataProvider:
   ├── Loads cached data from localStorage (if any)
   ├── Fires initial refresh: parallel calls to:
   │   ├── GET /api/v1/state/live        → trains, sections, conflicts, platforms
   │   ├── GET /api/v1/optimization/history → optimization run logs
   │   └── GET /api/v1/metrics           → KPI dashboard metrics
   └── Sets up 5-second polling interval (setInterval)
4. AppLayout renders:
   ├── Sidebar (tab navigation + conflict injection button)
   ├── Header (system status)
   └── Active tab content (Dashboard / TrainList / NetworkMap / ScheduleView / LogsView)
```

### C. Optimization Cycle (triggered by POST `/api/v1/optimization/run`)

```
1. Route handler (routes.py:run_optimization)
   └── Calls orchestrator.execute_cycle()

2. SimulationOrchestrator.execute_cycle() (simulator.py):
   ├── [Step 1-2] Build digital twin
   │   ├── state_engine.update_time(now)
   │   └── state_engine.snapshot_state()
   │       ├── Reads all trains + states from DB (via TrainRepository)
   │       ├── Reads all sections from DB (via SectionRepository)
   │       ├── Builds NetworkX graph (stations=nodes, sections=edges)
   │       └── Detects conflicts (headway/capacity violations)
   │
   ├── [Step 3] Apply disruptions (if any injected)
   │   └── Validates state integrity after disruption
   │
   ├── [Step 4] Generate ML predictions
   │   ├── For each train: predict delay (RandomForest regressor)
   │   └── For each section: predict congestion (RandomForest classifier)
   │
   ├── [Step 5] Run optimization (OR-Tools CP-SAT)
   │   ├── Build OptimizationSnapshot (trains, stops, sections, predictions)
   │   ├── Create CP model with constraints:
   │   │   ├── Capacity constraints (max trains per section)
   │   │   ├── Headway constraints (min time between trains)
   │   │   ├── Precedence variables (which train yields)
   │   │   └── Objective: minimize total weighted delay
   │   ├── Solve with time limit (default 30s)
   │   └── Generate explanation (optimizer_explanation.py)
   │       ├── Detect conflicts
   │       ├── Extract precedence decisions
   │       ├── Calculate objective improvement (before/after)
   │       └── Generate per-train actions
   │
   ├── [Step 6] Validate optimization result
   │   └── Check status is OPTIMAL/FEASIBLE, delay bounds reasonable
   │
   ├── [Step 7] Persist to database
   │   ├── Write optimization_logs row (with plan + explanation JSON)
   │   └── Update train_states (reduce delays, never increase)
   │
   ├── [Step 7b] Record historical data (ML training corpus growth)
   ├── [Step 7c] Check for ML drift → maybe retrain
   └── [Step 8] Calculate + persist KPIs
```

### D. Conflict Injection Flow (POST `/api/v1/conflicts/inject`)

```
1. Route handler fetches active trains from DB
2. Selects random trains, adds 10-40 min delay
3. Updates train_states directly in DB
4. Returns affected trains list
5. Frontend refreshes on next 5s poll → dashboard shows new conflicts
```

---

## 2. Dependency Chain

```
config.py (Settings)
    ↓
main.py (Engine, SessionLocal)
    ↓
┌─────────────────────────────────────────────────┐
│  Dependency Injection (per-request)              │
│  routes.py:get_db_session → SessionLocal()       │
│  routes.py:get_orchestrator → SimulationOrchestrator │
│  routes.py:get_state_engine → RailwayStateEngine │
│  routes.py:get_train_repo → TrainRepository      │
│  routes.py:get_section_repo → SectionRepository  │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  Service Layer                                   │
│  SimulationOrchestrator                          │
│    ├── RailwayStateEngine (state_engine.py)       │
│    ├── OptimizationService (optimizer.py)          │
│    │     └── generate_explanation (optimizer_explanation.py) │
│    └── PredictionService (predictor.py)            │
│          └── sklearn models (./models/*.pkl)       │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  Repository Layer                                │
│  TrainRepository → Train, TrainState, TrainSchedule │
│  SectionRepository → Section, Station              │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  ORM Layer (db_models.py)                        │
│  Station, Section, Train, TrainSchedule,          │
│  TrainState, OptimizationLog,                     │
│  HistoricalOperationalData, KPIMetric,            │
│  ManualOverride                                   │
└─────────────────────────────────────────────────┘
    ↓
  PostgreSQL (Supabase) or SQLite (dev)
```

---

## 3. Test Checklist

### Pre-flight
- [ ] `.env` file exists in `backend/` with `DATABASE_URL` set
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `npm install` in `frontend/` completes without errors

### Backend Startup
- [ ] `uvicorn app.main:app --port 8010` starts without errors
- [ ] Logs show: "Application startup complete"
- [ ] Logs show: "Database connected. Tables found: [...]"
- [ ] `GET http://localhost:8010/api/v1/health` returns `{"status": "healthy", ...}`
- [ ] `GET http://localhost:8010/health/ready` returns `{"status": "ready"}`
- [ ] `GET http://localhost:8010/api/docs` loads Swagger UI

### Frontend Startup
- [ ] `npm run dev` in `frontend/` starts on port 3001
- [ ] `http://localhost:3001` loads the dashboard
- [ ] No console errors about failed API calls (backend must be running)
- [ ] Dashboard shows train/section/conflict data

### Core API Endpoints
- [ ] `GET /api/v1/state/live` returns trains, sections, conflicts, platforms
- [ ] `GET /api/v1/metrics` returns KPI data (or 204 if no cycles run yet)
- [ ] `GET /api/v1/optimization/history` returns list (empty is OK)
- [ ] `POST /api/v1/conflicts/inject` returns `trains_affected > 0`
- [ ] `POST /api/v1/optimization/run` returns `status: "success"`
- [ ] `GET /api/v1/optimization/latest-plan` returns plan with `explanation` field
- [ ] `POST /api/v1/conflicts/reset` clears all delays

### Optimization Cycle Integrity
- [ ] After inject → optimize: `total_weighted_delay` decreases (or stays 0)
- [ ] After optimize: `explanation.conflicts_detected` has entries (if conflicts existed)
- [ ] After optimize: `explanation.decisions_made` has entries (if precedence was needed)
- [ ] After optimize: `explanation.objective_improvement.improvement_percent >= 0`
- [ ] Train states in DB: delays reduced or unchanged (never increased by optimizer)
- [ ] `optimization_logs` table has new row with `notes` JSON containing plan

### ML Pipeline
- [ ] `POST /api/v1/ml/train` trains models without error
- [ ] `GET /api/v1/ml/status` returns model info
- [ ] After training: `./models/delay_regressor.pkl` exists
- [ ] After training: `./models/congestion_classifier.pkl` exists

### No Race Conditions
- [ ] Two rapid `POST /optimization/run` calls don't corrupt state
  - (Each gets its own DB session via DI; SimulationOrchestrator is stateful per-request)
- [ ] Frontend 5s polling doesn't interfere with optimization writes
  - (Reads use separate sessions from writes)
- [ ] Manual override prevents optimization from running concurrently

### No Feature Conflicts
- [ ] Conflict injection + optimization don't fight each other
  - (Injection writes delays; optimization reduces them — one direction)
- [ ] Reset endpoint fully clears state for clean re-demo
- [ ] ML retraining doesn't block optimization cycle
  - (Wrapped in try/except, logged, never crashes cycle)

### Demo Flow (end-to-end)
```bash
# From backend/ directory:
python scripts/demo.py
```
- [ ] Script completes all 4 steps without errors
- [ ] Dashboard at http://localhost:3001 shows updated data
- [ ] Optimization Plan panel shows explanation sections

---

## 4. Clean Project Structure (Post-Audit)

```
mindicator hackathon/
├── AUDIT_REPORT.md              # Phase 1 diagnosis
├── EXECUTION_FLOW.md            # This document
├── docs/                        # All documentation
│   ├── BACKEND_COMPLETE.md
│   ├── OPTIMIZER_GUIDE.md
│   ├── PREDICTOR_GUIDE.md
│   ├── PREDICTOR_SUMMARY.md
│   ├── SIMULATOR_GUIDE.md
│   ├── APP_README.md
│   ├── CONFLICT_INJECTION_REFACTOR.md
│   ├── DEMO_GUIDE.md
│   └── JUDGES_DEMO_FINAL.md
├── backend/
│   ├── app/
│   │   ├── apis/
│   │   │   └── routes.py        # All API endpoints
│   │   ├── models/
│   │   │   ├── __init__.py      # Model exports
│   │   │   └── db_models.py     # 9 ORM models
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── train_repository.py
│   │   │   └── section_repository.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── state_engine.py
│   │   │   ├── optimizer.py
│   │   │   ├── optimizer_explanation.py
│   │   │   ├── predictor.py
│   │   │   └── simulator.py
│   │   ├── config.py
│   │   └── main.py              # FastAPI app + lifespan
│   ├── scripts/
│   │   └── demo.py              # Consolidated demo tool
│   ├── seed_data.py             # Database seeder
│   ├── requirements.txt
│   ├── .env.example
│   └── .gitignore
└── frontend/
    ├── src/
    │   ├── components/          # React components
    │   ├── context/
    │   │   └── LiveDataContext.tsx
    │   ├── utils/
    │   ├── App.tsx
    │   ├── api.ts
    │   ├── types.ts
    │   ├── main.tsx
    │   └── index.css
    ├── package.json
    └── index.html
```
