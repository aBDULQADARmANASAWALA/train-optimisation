# 🧠 PHASE 1 — SYSTEM DIAGNOSIS REPORT

## 1. Architecture Overview

### Entry Point
- **Backend**: `backend/app/main.py` → FastAPI app, started via `uvicorn app.main:app`
- **Frontend**: `frontend/src/main.tsx` → React/Vite app on port 3001

### Dependency Flow
```
main.py (FastAPI lifespan)
  ├── config.py (Settings from .env via pydantic-settings)
  ├── models/db_models.py (SQLAlchemy ORM: Station, Section, Train, TrainSchedule, TrainState, OptimizationLog)
  ├── repositories/
  │   ├── train_repository.py (TrainRepository)
  │   └── section_repository.py (SectionRepository)
  ├── services/
  │   ├── state_engine.py (RailwayStateEngine — NetworkX graph, occupancy tracking)
  │   ├── optimizer.py (OptimizationService — OR-Tools CP-SAT)
  │   ├── optimizer_explanation.py (generate_explanation — human-readable output)
  │   ├── predictor.py (PredictionService — sklearn RandomForest)
  │   └── simulator.py (SimulationOrchestrator — orchestration cycle)
  └── apis/routes.py (FastAPI router — all endpoints)

Frontend (React + Vite + TailwindCSS)
  ├── App.tsx (tab-based layout)
  ├── context/LiveDataContext.tsx (polling every 5s)
  ├── api.ts (API client → backend :8010)
  ├── types.ts (TypeScript interfaces)
  └── components/ (Dashboard, TrainList, NetworkMap, etc.)
```

---

## 2. Detected Structural Problems

### 🔴 CRITICAL Issues

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| C1 | **Broken Settings fields** | `reset_for_demo.py`, `check_and_reset_delays.py`, `demo_full_explanation.py` | These scripts reference `settings.supabase_db_user`, `settings.supabase_db_password`, `settings.supabase_db_host`, `settings.supabase_db_port`, `settings.supabase_db_name` — **none of which exist** in `config.py:Settings`. Will crash with `AttributeError` on every run. |
| C2 | **Schema mismatch: seed_data.py vs db_models.py** | `seed_data.py` | Seeds columns that don't exist in ORM models: `station_code`, `division`, `total_platforms`, `distance_km`, `max_speed_kmph` (on sections), `is_bidirectional`. Also references tables not in ORM: `train_routes`, `section_occupancy`, `platform_occupancy`, `historical_operational_data`, `platforms`. This script only works against a Supabase DB with a different schema than what `db_models.py` defines. |
| C3 | **Simulator writes to non-ORM tables** | `simulator.py` | Uses raw SQL `INSERT INTO` for: `manual_overrides`, `historical_operational_data`, `kpi_metrics`. These tables have no ORM model in `db_models.py`. If running against a fresh DB (e.g., SQLite), these writes will **fail silently** (caught + logged as warnings). |
| C4 | **reset_delays.py hardcoded SQLite path** | `reset_delays.py` | Hardcodes `sqlite:///./railway_optimization.db` which is a 0-byte empty file. Will never work against the real Supabase DB. |
| C5 | **generate_mock_live_data.py uses raw dotenv** | `generate_mock_live_data.py` | Uses `os.getenv("DATABASE_URL")` directly, bypassing `config.py`. Also uses raw SQL `DELETE FROM train_states` which is destructive. Enum values don't match (uses "IN_TRANSIT" vs ORM enum `in_transit`). |

### 🟡 MEDIUM Issues

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| M1 | **16 throwaway scripts cluttering root** | `backend/` root | `check_conflicts.py`, `check_and_reset_delays.py`, `check_schedule.py`, `debug_routes.py`, `demo_for_judges.py`, `demo_full_explanation.py`, `fetch_error.py`, `fetch_history_error.py`, `fetch_run_error.py`, `generate_mock_live_data.py`, `monitor_delays.py`, `reset_delays.py`, `reset_for_demo.py`, `test_db.py`, `test_explanation.py`, `test_full_explanation.py`, `test_opt.py`, `test_routes.py` — 18 scripts, most duplicating each other's functionality. |
| M2 | **Duplicate reset logic (5 variants)** | `reset_delays.py`, `reset_for_demo.py`, `check_and_reset_delays.py`, `demo_for_judges.py`, `demo_full_explanation.py` | Five different scripts that reset train delays, each with different DB connection logic, some broken. |
| M3 | **Duplicate demo logic (3 variants)** | `demo_for_judges.py`, `demo_full_explanation.py`, `test_full_explanation.py` | Three scripts that inject conflicts + run optimization + verify explanation. Nearly identical. |
| M4 | **Orphan data/output files** | `error.json`, `error_out.txt`, `history.json`, `history_error.json`, `metrics.json`, `opt_logs.json`, `out2.txt`, `out_opt.txt`, `out_opt_utf8.txt`, `result.json`, `railway_optimization.db` | Debug output files committed to repo. |
| M5 | **Orphan HTML files** | `swagger_ui.html`, `temp_docs.html` | Static HTML duplicating FastAPI's built-in docs. |
| M6 | **Empty directories** | `backend/models/`, `frontend/src/app/`, `frontend/src/assets/`, `frontend/src/features/`, `frontend/src/hooks/`, `frontend/src/pages/`, `frontend/src/services/`, `frontend/src/components/kpi-panel/`, etc. | Empty placeholder directories never used. |
| M7 | **Frontend mock data unused** | `frontend/src/data/mockData.ts` | Mock data file never imported by any component (all data comes from `LiveDataContext`). |
| M8 | **Frontend package.json has unnecessary deps** | `package.json` | `better-sqlite3`, `express`, `dotenv`, `@google/genai` — none are used by the Vite/React frontend. |
| M9 | **Unused `asyncio` import** | `check_schedule.py`, `test_opt.py` | Import `asyncio` but never use it. |
| M10 | **examples/ directory** | `backend/examples/` | 7 large testing files (80+ KB total) that duplicate what the test scripts already do. Never imported by the main app. |

### 🟢 MINOR Issues

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| N1 | **Indentation inconsistency** | `section_repository.py` | `signalling_type` lines at L103, L136, L171 have extra indentation. |
| N2 | **Root markdown clutter** | Root | `CONFLICT_INJECTION_REFACTOR.md`, `DEMO_GUIDE.md`, `JUDGES_DEMO_FINAL.md` — process docs that should be in a `docs/` folder or removed. |
| N3 | **Backend markdown clutter** | `backend/` | `BACKEND_COMPLETE.md`, `OPTIMIZER_GUIDE.md`, `PREDICTOR_GUIDE.md`, `PREDICTOR_SUMMARY.md`, `SIMULATOR_GUIDE.md` — internal docs mixed with code. |
| N4 | **`openapi_current.json` stale snapshot** | `backend/` | Static OpenAPI dump; FastAPI generates this dynamically at `/api/openapi.json`. |

---

## 3. Module Interaction Map

```
[Frontend :3001]
    │ polls every 5s
    ▼
[Backend :8010]  ─── FastAPI app
    │
    ├── GET  /api/v1/state/live      → StateEngine.snapshot_state()
    ├── GET  /api/v1/metrics         → DB query (OptimizationLog + TrainState)
    ├── GET  /api/v1/optimization/history → DB query (OptimizationLog)
    ├── GET  /api/v1/optimization/latest-plan → DB query (OptimizationLog.notes JSON)
    ├── POST /api/v1/optimization/run → SimulationOrchestrator.execute_cycle()
    ├── POST /api/v1/conflicts/inject → Direct DB manipulation
    ├── POST /api/v1/conflicts/reset  → Direct DB manipulation
    ├── POST /api/v1/override        → SimulationOrchestrator.set_manual_override()
    ├── POST /api/v1/ml/train        → PredictionService.train_models()
    ├── GET  /api/v1/ml/status       → PredictionService.get_model_info()
    └── GET  /api/v1/status          → SimulationOrchestrator.get_execution_summary()
```

### Silent Failure Points
1. **`_record_historical_data()`** — writes to `historical_operational_data` table via raw SQL. Fails silently if table doesn't exist.
2. **`_persist_kpi_metrics()`** — writes to `kpi_metrics` table. Same issue.
3. **`set_manual_override()`** — writes to `manual_overrides` table. Same issue.
4. **All 3 are caught with `except Exception` + `logger.warning()` + `rollback()`** — the user sees no error.

---

## 4. What Works vs What Doesn't

### ✅ Core pipeline works:
- FastAPI app starts correctly via `uvicorn app.main:app`
- DB connection via `DATABASE_URL` in `.env`
- All API routes register correctly
- Frontend connects and polls backend
- Optimization cycle (inject → optimize → explain) works end-to-end through API endpoints

### ❌ What fails:
- Any standalone script that references non-existent Settings fields (C1)
- `reset_delays.py` — hardcoded wrong DB (C4)
- `generate_mock_live_data.py` — bypasses config, enum mismatch (C5)
- `seed_data.py` against ORM-created DB — schema mismatch (C2)
- Silent failures on `historical_operational_data`, `kpi_metrics`, `manual_overrides` writes (C3)
