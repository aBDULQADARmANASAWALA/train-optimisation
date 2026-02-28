# Dashboard Consistency Audit — Final Report

**Date:** 2025-03-01
**Status:** ✅ ALL 5 PHASES COMPLETE — TypeScript compiles clean (0 errors)

---

## PHASE 1: Single Source of Truth Verification

**7 issues found and fixed.**

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| P1-1 | Hardcoded `trendData` array (static fake chart data) | Medium | `Dashboard.tsx` | Removed entirely — bar chart now uses live `trains` data |
| P1-2 | Dual delay computation: `metrics.total_weighted_delay_minutes` vs `trains.reduce()` could diverge | High | `Dashboard.tsx:42-44` | Unified to single source: always `trains.reduce()` from `/state/live` |
| P1-3 | `totalDelayReduced` summed raw `total_weighted_delay` (current delay, NOT reduction) — semantically wrong | High | `Dashboard.tsx:48` | Replaced with `totalConflictsResolved` — accurate metric from `optimization_logs.conflicts_detected` |
| P1-4 | `LogsView` used entirely hardcoded `MOCK_LOGS` — no real data | Medium | `LogsView.tsx` | Rewrote to generate logs from `LiveDataContext` (trains, sections, conflicts, runs) |
| P1-5 | `ScheduleView` fabricated arrival times with `new Date() + index * 10` | High | `ScheduleView.tsx` | Rewrote to show real accumulated delays from live train state |
| P1-6 | Safety Net "MANUAL OVERRIDE" button only toggled local React state — no API call | High | `Sidebar.tsx` | Wired to `POST /api/v1/override` with loading guard |
| P1-7 | `/metrics` endpoint set `conflicts_avoided = conflicts_detected` (same value) | Medium | `routes.py:547` | Set `conflicts_avoided = 0` (backend doesn't track this separately) |

### Data Flow Map (verified)

```
DB (train_states, optimization_logs, sections, stations)
  ↓
Backend Routes (/state/live, /metrics, /optimization/history, /optimization/latest-plan)
  ↓
Frontend api.ts (typed mapping layer)
  ↓
LiveDataContext (single polling loop, 5s interval, all 4 endpoints)
  ↓
All components consume via useLiveData() hook
```

---

## PHASE 2: Optimize Button Validation

**Verdict: ✅ Optimization is real and correct.**

### Execution Trace

1. `Dashboard.tsx:handleOptimization()` → sets `isOptimizing=true`, disables button
2. `api.runOptimization()` → `POST /api/v1/optimization/run`
3. Backend: `orchestrator.execute_cycle()` runs full 8-step pipeline
4. CP-SAT solver minimizes weighted delay with capacity/headway/safety constraints
5. `_persist_updated_states()` writes `optimization_logs` row AND updates `train_states`
6. Delay reduction policy: `new_delay = min(current_delay, min_opt_delay)` — delays can only go DOWN
7. Frontend: `refreshData()` re-fetches all 4 data sources → dashboard updates atomically

### Verified Properties
- **Real DB mutation**: optimizer writes to `optimization_logs` AND `train_states`
- **Delay monotonically decreases**: `min()` policy prevents optimizer from increasing delay
- **Deterministic**: CP-SAT with fixed parameters produces deterministic results
- **No stale data**: `refreshData()` after optimization ensures fresh state

---

## PHASE 3: Global Dashboard Sync Check

**1 issue found and fixed.**

| # | Issue | Fix |
|---|-------|-----|
| P3-1 | `OptimizationPlanPanel` had independent `useEffect` fetch — not part of unified polling | Moved plan fetch into `LiveDataContext.refreshData()`. Panel now consumes `plan` from context. |

### Final Component → Data Source Mapping

| Component | Data | Source |
|-----------|------|--------|
| Dashboard (KPIs) | conflicts, trains, sections, runs | LiveDataContext |
| Header | conflicts, metrics | LiveDataContext |
| TrainList | trains | LiveDataContext |
| NetworkMap | sections, trains, platforms | LiveDataContext |
| ScheduleView | trains | LiveDataContext |
| LogsView | trains, sections, conflicts, runs | LiveDataContext |
| OptimizationPlanPanel | plan, loading | LiveDataContext |
| Sidebar | (no data consumption, only actions) | — |

**All components now consume from the single `LiveDataContext` provider.** Zero independent fetches.

---

## PHASE 4: Button Functionality Audit

**3 placeholder buttons disabled, 3 active buttons verified.**

### Active Buttons (all verified safe)

| Button | Guard | Race Protection |
|--------|-------|-----------------|
| Force Optimization | `disabled={isOptimizing}` | `isOptimizing` state + `finally` block |
| Add Sample Conflicts | `disabled={injectState === 'loading'}` | Early return + disabled attr |
| Manual Override | `disabled={overrideLoading}` | `overrideLoading` ref + early return |

### Placeholder Buttons (disabled with tooltips)

| Button | File | Status |
|--------|------|--------|
| Export Report | `Dashboard.tsx` | `disabled` + "coming soon" tooltip |
| View Supabase | `LogsView.tsx` | `disabled` + tooltip |
| Clear Logs | `LogsView.tsx` | `disabled` + tooltip |
| View Details (per train) | `TrainList.tsx` | `disabled` + tooltip |

---

## PHASE 5: Duplication & Random Increment Protection

**3 issues found and fixed.**

| # | Issue | Fix |
|---|-------|-----|
| P5-1 | `refreshData` closure captured by `setInterval` | Safe — uses `setData(prev => ...)` functional updater |
| P5-2 | No guard against overlapping concurrent `refreshData` calls | Added `refreshInFlight` ref guard in `LiveDataContext` |
| P5-3 | Conflict injection `+= delay` with no cap — unbounded growth | Capped at `min(120.0, existing + new)` in `routes.py` |

### Verified Safe Patterns

- **setInterval**: single instance, `clearInterval` in cleanup, `[]` deps
- **setTimeout** (Sidebar): purely cosmetic label reset, no state mutation
- **Data replacement**: `setData` always does full array replacement (`=`), never `.push()`
- **No shared mutable state on backend**: each request gets fresh orchestrator via DI
- **localStorage cache**: warm start only, immediately overwritten by first poll

---

## Files Modified

| File | Changes |
|------|---------|
| `frontend/src/context/LiveDataContext.tsx` | Added plan to state, added `refreshInFlight` guard, added `useRef` import |
| `frontend/src/components/Dashboard.tsx` | Removed fake data, unified delay source, fixed KPI card, cleaned imports |
| `frontend/src/components/LogsView.tsx` | Replaced mock logs with live data, disabled placeholder buttons |
| `frontend/src/components/ScheduleView.tsx` | Rewrote to show real delay data instead of fabricated times |
| `frontend/src/components/Sidebar.tsx` | Wired Manual Override to backend API with loading guard |
| `frontend/src/components/TrainList.tsx` | Disabled placeholder "View Details" button |
| `frontend/src/components/OptimizationPlanPanel.tsx` | Consumes plan from LiveDataContext instead of independent fetch, fixed TS key prop |
| `backend/app/apis/routes.py` | Fixed `conflicts_avoided` metric, capped injection delay at 120m |

**TypeScript compilation: 0 errors.**
