# SimulationOrchestrator - Real-Time Execution Brain

## Overview

This is the **orchestration brain** that ties together all services into a cohesive real-time optimization loop. It runs as a background job, executing cycles of:

1. **State Fetching** - Current network state
2. **Digital Twin** - In-memory graph representation
3. **Prediction** - ML forecasts for delays/congestion
4. **Optimization** - CP-SAT schedule optimization
5. **Validation** - Schedule feasibility check
6. **Persistence** - Database updates
7. **Metrics** - KPI calculation and logging

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│      SimulationOrchestrator (Main Loop)         │
│                                                 │
│  [1] Fetch State                                │
│        ↓                                        │
│  [2] Build Digital Twin (StateEngine)           │
│        ↓                                        │
│  [3] Apply Disruptions (if any)                 │
│        ↓                                        │
│  [4] Generate Predictions (Predictor)           │
│        ↓                                        │
│  [5] Optimize Schedule (Optimizer)              │
│        ↓                                        │
│  [6] Validate Result                           │
│        ├─ Valid? → [7] Persist to DB           │
│        └─ Invalid? → Rollback                  │
│        ↓                                        │
│  [8] Calculate KPIs                            │
│        ↓                                        │
│  [9] Log Result                                │
│        ↓                                        │
│  Wait rolling_step_minutes → Repeat             │
└─────────────────────────────────────────────────┘
```

---

## Core Responsibilities

### Cycle Execution: `execute_cycle() → CycleResult`

Runs one complete orchestration cycle with error handling.

**Process**:
1. Fetch current state from repositories
2. Update StateEngine with current time
3. Apply active disruptions
4. Generate ML predictions
5. Run optimizer (or use manual override)
6. Validate result
7. Persist to database if valid
8. Calculate KPIs
9. Log and return result

**Returns**: `CycleResult` with:
- `cycle_number`: Which cycle this was
- `timestamp`: When executed
- `status`: SUCCESS, VALIDATION_FAILED, ERROR, etc.
- `state_engine_snap`: Current state
- `predictions`: ML predictions
- `optimization_result`: CP-SAT solution
- `validated`: Whether passed validation
- `kpis`: Key performance indicators
- `duration_seconds`: Execution time

### Disruption Injection: `inject_disruption(...)`

Simulate operational disruptions for scenario testing.

**Disruption Types**:
```python
DisruptionType.TRAIN_DELAY           # Add delay minutes to train
DisruptionType.CAPACITY_REDUCTION    # Reduce section capacity %
DisruptionType.SECTION_CLOSURE       # Block entire section
DisruptionType.PLATFORM_FAILURE      # Make platform unavailable
```

**Example**:
```python
orchestrator.inject_disruption(
    disruption_type=DisruptionType.TRAIN_DELAY,
    affected_id=train_uuid,
    magnitude=10.0,  # 10 minutes
    duration_minutes=30,
    start_time=datetime.utcnow(),
)
```

Active disruptions are applied at step [3] each cycle if their time window is active.

### Manual Override: `set_manual_override(enabled: bool)`

Emergency control mode - uses last known good schedule instead of optimizing.

**Used for**:
- Emergency response when optimization fails
- Testing "do no harm" mode
- Reverting to safe schedule

```python
orchestrator.set_manual_override(True)   # Use cached schedule
orchestrator.execute_cycle()             # Won't optimize
orchestrator.set_manual_override(False)  # Resume normal operation
```

---

## KPI Monitoring

### KPISnapshot dataclass

Captures performance metrics for each cycle:

```python
@dataclass
class KPISnapshot:
    cycle_timestamp: datetime
    cycle_number: int
    total_weighted_delay_minutes: float  # Σ(priority × delay)
    average_section_utilization_percent: float  # 0-100%
    conflicts_detected: int  # Current cycle
    conflicts_avoided: int  # Prevented by optimization
    trains_delayed: int  # > 0.5 min late
    trains_on_time: int  # <= 0.5 min late
    optimization_runtime_seconds: float  # Solver time
    prediction_accuracy_mae: float  # Mean absolute error
    schedule_adherence_percent: float  # 0-100%
```

### KPI Access Methods

**Latest KPIs**:
```python
latest_kpis = orchestrator.get_latest_kpis()
print(f"Delay: {latest_kpis.total_weighted_delay_minutes}min")
print(f"Utilization: {latest_kpis.average_section_utilization_percent}%")
```

**Trend Analysis**:
```python
trends = orchestrator.get_kpi_trends(periods=10)
for kpi in trends:
    print(f"Cycle {kpi.cycle_number}: {kpi.total_weighted_delay_minutes}min")
```

**Execution Summary**:
```python
summary = orchestrator.get_execution_summary()
print(f"Success Rate: {summary['success_rate']:.1%}")
print(f"Total Conflicts Avoided: {summary['total_conflicts_avoided']}")
```

---

## Validation Strategy

### What Gets Validated

1. **Feasibility**: Solution is feasible (not infeasible)
2. **Constraint Satisfaction**: No violations
3. **Reasonable Delays**: Total delay within bounds
4. **Consistency**: Schedule respects timing constraints

### Validation Flow

```
Optimization Result
    ↓
[Check if feasible?]
    ├─ No → INVALID
    └─ Yes → Continue
    ↓
[Check delay magnitude?]
    ├─ Excessive → INVALID
    └─ Reasonable → Continue
    ↓
[Check constraints?]
    ├─ Violated → INVALID
    └─ Satisfied → VALID
    ↓
Valid Schedule
    ↓
Persist to Database
```

If validation fails:
- Database NOT updated
- Last known good schedule retained
- Error logged for investigation
- Status returned to caller

---

## Execution Model

### Design Patterns

**1. Transactional**: All-or-nothing updates
- Database changes only if validation passes
- Automatic rollback on errors
- No partial updates

**2. Idempotent**: Same cycle always produces same result (given same inputs)
- Enables safe retries
- Reproducible for debugging
- Time-based (not clock-based)

**3. Rolling Horizon**: Fixed-size optimization window
- Next cycle shifts window forward by `rolling_step_minutes`
- StateEngine auto-cleans old records
- Warm-start for faster convergence

**4. Background Job**: Designed for scheduler execution
```bash
# Example: Run every 5 minutes
*/5 * * * * /path/to/orchestration_runner.py
```

### Cycle Execution Flow

```
Start Orchestration Cycle
    ↓
[1] Fetch Live State
    - Load current trains, sections from DB
    - Input: repositories
    - Output: Raw data
    ↓
[2] Build Digital Twin
    - StateEngine builds in-memory graph
    - Input: Raw state data
    - Output: state_snapshot
    ↓
[3] Apply Disruptions
    - Check active disruptions
    - Modify state_snapshot
    - Example: add 10min delay to train
    ↓
[4] Generate Predictions
    - Predictor forecasts delays/congestion
    - Input: state_snapshot
    - Output: predictions dictionary
    ↓
[5] Optimize (or Override)
    - IF manual_override:
        Use last known good
    - ELSE:
        Run CP-SAT optimizer
    - Input: state_snapshot, predictions
    - Output: optimization_result
    ↓
[6] Validate
    - Check feasibility
    - Check constraint satisfaction
    - Decision: Valid or Invalid
    ↓
[7] Persist (if valid)
    - Update train states in DB
    - Record optimization result
    - Commit transaction
    ↓
[8] Calculate KPIs
    - Compute metrics
    - Store in history
    ↓
[9] Log & Return
    - Log summary to file/console
    - Return CycleResult
    ↓
End of Cycle (wait for next scheduled run)
```

---

## Integration with Other Services

```
SimulationOrchestrator
    ├── Uses: TrainRepository
    │   └── get_active_trains()
    │   └── get_train_schedule()
    │   └── update_train_state()
    │
    ├── Uses: SectionRepository
    │   └── get_all_sections()
    │   └── get_section_by_id()
    │
    ├── Uses: RailwayStateEngine
    │   └── snapshot_state()
    │   └── detect_conflicts()
    │   └── update_time()
    │
    ├── Uses: OptimizationService
    │   └── optimize()
    │   └── Returns: optimized schedule
    │
    └── Uses: PredictionService
        └── predict_delay()
        └── predict_congestion()
        └── Returns: forecasts with confidence
```

---

## Performance Characteristics

### Typical Cycle Time
```
[1] Fetch State:          20ms
[2] Build Twin:           50ms
[3] Apply Disruptions:    5ms
[4] Generate Predictions: 100ms
[5] Optimize (CP-SAT):    2000-5000ms (varies)
[6] Validate:             10ms
[7] Persist:              30ms
[8] Calculate KPIs:       20ms
[9] Log:                  5ms
───────────────────────────────
Total Per Cycle:          2.5-10 seconds
```

**For 100 trains**:
- State fetch: ~20ms
- Predictions: ~100ms (1ms per train)
- Optimization: ~3-5s (CPU-bound)
- **Total: ~5-6 seconds**

Fits easily into a 5-minute rolling window!

---

## Error Handling

### Graceful Degradation

```
Normal Flow:
  optimize() → valid → persist

If optimizer fails:
  optimize() → None → use_manual_override → persist_last_known_good

If validation fails:
  optimize() → invalid → DON'T_PERSIST → log_error → continue

If database fails:
  persist() → exception → rollback → return error
```

### Logged Errors

All failures are logged with context:
```
ERROR: Optimization failed: Infeasible problem
  Reason: Section C→N: 4 trains exceed capacity 3
  Cycle: 42
  Timestamp: 2024-02-28T10:30:45
  Action: Using manual override
```

---

## Testing & Scenarios

### Example: Normal Operation
```python
orchestrator = SimulationOrchestrator(...)
for i in range(10):
    result = orchestrator.execute_cycle()
    assert result.status == ExecutionStatus.SUCCESS
    assert result.kpis.total_weighted_delay < 10
```

### Example: Disruption Response
```python
orchestrator.inject_disruption(
    DisruptionType.TRAIN_DELAY,
    train_id,
    magnitude=15.0,  # 15 min delay
    duration_minutes=60
)
result = orchestrator.execute_cycle()
assert result.kpis.conflicts_avoided > 0
```

### Example: Manual Override
```python
orchestrator.set_manual_override(True)
result = orchestrator.execute_cycle()
assert result.status == ExecutionStatus.SUCCESS
# Uses cached schedule, doesn't crash
orchestrator.set_manual_override(False)
```

---

## Deployment

### As Background Job

**Schedule**: Every 5 minutes
```bash
*/5 * * * * /app/scripts/run_orchestration_cycle.py
```

**Monitoring**:
```python
# Check success rate
summary = orchestrator.get_execution_summary()
if summary['success_rate'] < 0.95:
    alert("Low orchestration success rate")

# Monitor KPIs
latest = orchestrator.get_latest_kpis()
if latest.total_weighted_delay > 50:
    alert("High delay accumulation")
```

**Logs**:
- One entry per cycle (5-minute intervals)
- Includes status, KPIs, runtime
- Errors logged immediately with context

---

## Future Enhancements

1. **Adaptive Rolling Horizon**: Adjust window size based on demand
2. **Multi-Objective Optimization**: Weight energy, emissions alongside delay
3. **Real-Time Feedback Loop**: Track actual vs predicted, retrain models
4. **Scenario Planning**: Test multiple disruptions simultaneously
5. **Human-in-the-Loop**: Dispatcher approval for major changes
6. **Distributed Optimization**: Split across multiple solvers for large networks

---

**This is your railway optimization neural center** - it processes all information and makes moment-by-moment decisions to keep trains running smoothly. 🚂✨
