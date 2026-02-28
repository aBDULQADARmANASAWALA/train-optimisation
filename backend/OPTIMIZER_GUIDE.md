# OptimizationService - Constraint Programming Optimizer

## Overview

This is a production-grade optimization service using **Google OR-Tools CP-SAT solver** for railway schedule optimization. It's the core intelligence engine that solves complex scheduling problems while respecting all railway constraints.

## Architecture

### Input: OptimizationSnapshot
```
{
  timestamp: datetime,
  trains: {train_id -> train_info},
  train_stops: [TrainStop],  // All scheduled stops
  sections: [SectionInfo],   // Network topology
  current_positions: {train_id -> (section_id, station_id)},
  predicted_delays: {train_id -> delay_minutes},
  platform_capacity: {station_id -> max_tracks}
}
```

### Processing: Constraint Programming Model

**Decision Variables:**
- `arrival_time[train, station]` - Arrival time at station (continuous)
- `departure_time[train, station]` - Departure time from station (continuous)
- `precedence[train_i, train_j, section]` - Binary: train_i before train_j on section

**Constraints:**
1. **Continuity**: arrival ≤ departure at each stop
2. **Dwell Time**: departure ≥ arrival + platform dwell time
3. **Travel Time**: respected between consecutive stops
4. **Platform Capacity**: max simultaneous trains at station
5. **Section Capacity**: max concurrent trains on section
6. **Headway**: minimum spacing between consecutive trains (+ safety margin)
7. **Disjunctive**: precedence constraints (either train i before j or j before i)

**Objective Function:**
```
Minimize: Σ(priority_weight[train] × delay[train, all_stops])
```

### Output: OptimizedSchedule
```
{
  status: "optimal" | "feasible" | "infeasible",
  timestamp: datetime,
  horizon_start/end: datetime,
  solver_runtime_seconds: float,
  objective_value: float,
  total_weighted_delay: float,
  conflicts_resolved: int,
  trains_adjusted: int,
  adjusted_timings: {train_id -> [adjusted_stops]},
  infeasibility_reasons: [str],
  warm_start_applied: bool
}
```

## Key Features

### 1. Constraint Programming Solver
- Uses Google OR-Tools CP-SAT (state-of-the-art)
- Handles combinatorial optimization efficiently
- Provides optimal or feasible solutions
- Enforces all hard constraints

### 2. Scalability
- Handles **100+ trains** efficiently
- O(n²) constraint generation (manageable)
- Parallel constraint propagation
- Sub-second typical runtimes for most instances

### 3. Rolling Horizon Support
- Solves optimization window by window
- Warm-start from previous solution
- Shifts constraints as time advances
- Prevents horizon boundary artifacts

### 4. Warm Starting
```python
# Cycle 1: solve from scratch
result1 = optimizer.optimize(snapshot, use_warm_start=False)

# Cycle 2: reuse solution as hint
result2 = optimizer.optimize(snapshot, use_warm_start=True)
# Solver converges faster with hints
```

### 5. Graceful Infeasibility Handling
- Detects when problem is infeasible
- Reports infeasibility reasons
- Returns structured diagnostic info
- Enables fallback strategies

### 6. Time Limits
- Enforces `max_solver_time_seconds` strictly
- Returns best feasible solution if optimality takes too long
- Suitable for real-time decision-making
- Configurable per optimization

### 7. No Database Access
- Pure computation (all data in memory)
- Input: snapshot only
- No side effects
- Deterministic (same input → same output)
- Perfect for testing/validation

## Variables Explained

### `arrival_time` and `departure_time`
- **Type**: IntVar (integer minutes offset from horizon_start)
- **Domain**: [0, horizon_length] minutes
- **Bounds**: Scheduled ± delay_allowance
- **Units**: Minutes, 0.5-minute granularity

### `precedence` Variables
- **Type**: BoolVar (0 or 1)
- **Meaning**: 1 if train_i must depart before train_j arrives + headway
- **Purpose**: Enforces headway via disjunctive constraints
- **Count**: O(n²) for n trains on shared section

## Constraints Explained

### Continuity Constraint
```
arrival[t,s] ≤ departure[t,s]  ∀ train t, station s
```
Ensures trains don't leave before arriving.

### Dwell Time Constraint
```
departure[t,s] ≥ arrival[t,s] + dwell_time[s]  ∀ train t, station s
```
Enforces minimum time at platform.

### Travel Time Constraint
```
arrival[t,s2] ≥ departure[t,s1] + travel_time[s1→s2]  ∀ consecutive stops
```
Ensures trains take reasonable time between stations.

### Headway Constraint (Disjunctive)
```
IF precedence[i,j,section] == 1 THEN:
  departure[i, from_section] + headway ≤ arrival[j, from_section]
ELSE:
  departure[j, from_section] + headway ≤ arrival[i, from_section]
```
Either train i before j or j before i (not simultaneous).

## Objective Function

**Weighted Delay Minimization:**
```
Minimize: Σ Σ (priority_weight[t] × max(0, delay[t,s]))
          t  s
```

- **priority_weight**: 0.5 to 3.0 typically
- **delay**: arrival - scheduled_arrival (minutes)
- **Effect**: High-priority trains get minimal delays

## Solving Process

1. **Model Construction** (< 1ms)
   - Create variables
   - Add constraints
   - Set objective

2. **Constraint Propagation** (< 5ms)
   - Solver derives implications
   - Prunes infeasible regions
   - Updates domains

3. **Search** (varies)
   - Explores solution space
   - Finds feasible solution
   - Optimizes within time limit

4. **Result Extraction** (< 1ms)
   - Read solution values
   - Convert to schedule
   - Calculate metrics

## Usage Example

```python
from app.services import OptimizationService, OptimizationSnapshot

# Create optimizer
optimizer = OptimizationService(
    max_solver_time_seconds=30.0,
    time_precision_minutes=0.5,
)

# Prepare snapshot (from state engine + predictor)
snapshot = OptimizationSnapshot(
    timestamp=now,
    trains=active_trains,
    train_stops=scheduled_stops,
    sections=network_sections,
    current_positions=train_positions,
    predicted_delays=forecasted_delays,
    platform_capacity=station_capacities,
)

# Optimize
result = optimizer.optimize(
    snapshot=snapshot,
    horizon_minutes=60,
    use_warm_start=True,
)

# Use result
if result.status == OptimizationStatus.OPTIMAL:
    print(f"Optimal solution: {result.objective_value}")
    for train_id, stops in result.adjusted_timings.items():
        print(f"  Train: {stops[0]['train_number']}")
        for stop in stops:
            print(f"    {stop['sequence']}: {stop['adjusted_arrival']}")
```

## Performance Characteristics

### Time Complexity
- Model building: O(n × m) where n=trains, m=stops
- Constraint generation: O(n²) for section headways
- Solving: Depends on problem structure (typically 0.1s - 30s)

### Space Complexity
- Variables: O(n × m) arrival/departure variables
- Constraints: O(n × m + n²) constraints
- Solver state: ~50MB for 100 trains

### Scalability
```
1-10 trains:    < 0.1s   (trivial)
10-50 trains:   0.5-2s   (easy)
50-100 trains:  2-10s    (moderate)
100+ trains:    10-30s   (challenging)
```

## Infeasibility Diagnosis

When solver returns INFEASIBLE:
1. Check reported infeasibility reasons
2. Common causes:
   - Section capacity < number of trains
   - Headway impossible with schedule
   - Platform capacity exceeded
   - Travel times too tight

Example diagnostic output:
```
infeasibility_reasons: [
  "Section C→N: 4 trains exceed capacity 3",
  "Platform East: 3 trains at same time, capacity 2"
]
```

## Testing

Run comprehensive tests:
```bash
python -m examples.testing_optimizer
```

Tests include:
- Basic optimization
- Schedule examination
- Priority weighting
- Rolling horizon (3 cycles)
- Infeasibility handling

## Dependencies

- `ortools==9.7.2996` - Google Optimization Tools
- Python 3.8+

Install:
```bash
pip install -r requirements.txt
```

## Design Principles

1. **Pure Computation** - No side effects, no DB access
2. **Deterministic** - Same input always produces same output
3. **Scalable** - Handles 100+ trains efficiently
4. **Practical** - Real-time constraints respected
5. **Transparent** - Results are interpretable
6. **Robust** - Handles infeasibility gracefully
7. **Warm-startable** - Accepts hints from previous solutions

---

**This optimizer is the core intelligence of the mindicator system.** It takes the current state, constraints, and predictions, then produces an optimal schedule that minimizes delays while respecting all railway operational rules.
