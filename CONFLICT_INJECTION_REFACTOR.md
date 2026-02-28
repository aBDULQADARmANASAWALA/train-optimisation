# Conflict Injection Refactor - Summary

## ✅ All Requirements Implemented

### 1. Probabilistic Injection (10-20% chance per cycle)
- **Location**: `SimulationOrchestrator.__init__()` line 139
- **Implementation**: `self.conflict_injection_probability = 0.15` (15% chance)
- **Usage**: `_apply_current_disruptions()` line 392 checks `random.random() > self.conflict_injection_probability`

### 2. Affects Only Trains Within Optimization Horizon
- **Location**: `_apply_train_delay_disruption()` lines 425-443
- **Implementation**: Checks if any upcoming stop is within `now` to `horizon_end` window
- **Behavior**: Skips injection if train not within horizon

### 3. Never Modifies Historical/Past Events
- **Location**: `_apply_train_delay_disruption()` lines 425-443
- **Implementation**: Only considers stops with `now <= arr_dt <= horizon_end`
- **Behavior**: Past events are excluded from injection

### 4. Never Produces Negative Delays
- **Location**: `_apply_train_delay_disruption()` line 458
- **Implementation**: `new_delay = max(0.0, new_delay)`
- **Validation**: `validate_state_integrity()` lines 367-370 checks for negative delays

### 5. Safeguards Implemented

#### a. Delay Cannot Be < 0
- **Line 458**: `new_delay = max(0.0, new_delay)`
- **Validation**: `validate_state_integrity()` checks all trains

#### b. Delay Increment Per Cycle Capped (max +5 minutes)
- **Configuration**: Line 140 `self.max_delay_increment_per_cycle = 5.0`
- **Enforcement**: Line 449 `delay_increment = min(disruption.magnitude, self.max_delay_increment_per_cycle)`

#### c. Total Delay Capped Per Train (max 60 minutes)
- **Configuration**: Line 141 `self.max_total_delay_per_train = 60.0`
- **Enforcement**: Lines 452-455 `new_delay = min(current_delay + delay_increment, self.max_total_delay_per_train)`

### 6. Injection Does NOT Run Multiple Times Per Cycle
- **Location**: `Disruption` dataclass line 52, `_apply_current_disruptions()` lines 386-389
- **Implementation**: `applied_cycles: Set[int]` tracks which cycles applied the disruption
- **Check**: `if self.cycle_count in disruption.applied_cycles: continue`
- **Mark**: Line 402 `disruption.applied_cycles.add(self.cycle_count)`

### 7. Does NOT Stack Repeatedly Without Reset
- **Location**: Lines 461-464
- **Implementation**: Checks `actual_increment = new_delay - current_delay`
- **Behavior**: If `actual_increment <= 0`, returns False (no injection)

### 8. Does NOT Modify Already Optimized Times
- **Location**: `_apply_current_disruptions()` returns modified state
- **Implementation**: Injection happens BEFORE optimization (Step 3), optimization happens in Step 5
- **Flow**: Disruption → Validation → Prediction → Optimization

### 9. Structured Logging Added

#### Train Delay Injection Logging (lines 471-478)
```python
logger.warning(
    f"CONFLICT_INJECTED: train_id={disruption.affected_id}, "
    f"train_number={train_number}, "
    f"delay_added={actual_increment:.1f}min, "
    f"total_delay={new_delay:.1f}min, "
    f"reason=disruption_injection, "
    f"cycle={self.cycle_count}"
)
```

#### Capacity Reduction Logging (lines 503-509)
```python
logger.warning(
    f"CONFLICT_INJECTED: section_id={disruption.affected_id}, "
    f"capacity_reduced={original_capacity}->{new_capacity}, "
    f"reduction_pct={disruption.magnitude:.1f}%, "
    f"reason=capacity_reduction, "
    f"cycle={self.cycle_count}"
)
```

### 10. Validation Method: `validate_state_integrity()`
- **Location**: Lines 352-418
- **Returns**: `Dict[str, Any]` with `valid`, `errors`, `checks_performed`

#### Check 1: No Negative Delays (lines 367-370)
```python
for train_id, train_info in self.state_engine.trains.items():
    delay = train_info.get("accumulated_delay_minutes", 0.0)
    if delay < 0:
        errors.append(f"Train {train_id} has negative delay: {delay:.1f}min")
```

#### Check 2: No Overlapping Section Occupancy (lines 373-388)
```python
for section_id, occupants in self.state_engine.section_occupancy.items():
    capacity = edge_data.get("capacity", 1)
    if len(occupants) > capacity:
        errors.append(f"Section {section_id} capacity violation...")
```

#### Check 3: No Time-Travel (lines 391-407)
```python
if dep_dt < arr_dt:
    errors.append(f"Train {train_id} time-travel violation...")
```

### 11. Injection is Isolated
- **Location**: `_apply_current_disruptions()` lines 424-511
- **Implementation**: 
  - Does NOT modify DB directly
  - Returns `Optional[Dict]` (modified state or None)
  - Orchestrator receives modified state in `execute_cycle()` line 179-181
- **Flow**: `modified_state = self._apply_current_disruptions(state_snapshot)`

### 12. Deterministic Behavior with Random Seed
- **Location**: `__init__()` lines 142-144
- **Implementation**:
```python
self.random_seed = random_seed
if random_seed is not None:
    random.seed(random_seed)
```
- **Usage**: Constructor accepts `random_seed: Optional[int] = None`

## Architecture Improvements

### Separation of Concerns
1. **`_apply_current_disruptions()`**: Orchestrates disruption application
2. **`_apply_train_delay_disruption()`**: Handles train delay logic with safeguards
3. **`_apply_capacity_reduction_disruption()`**: Handles capacity reduction logic
4. **`validate_state_integrity()`**: Validates state after injection

### Execution Flow
```
execute_cycle()
  ↓
Build state snapshot
  ↓
_apply_current_disruptions(state_snapshot) → modified_state
  ├─ Check active disruptions
  ├─ Probabilistic filter (15%)
  ├─ Prevent duplicate application per cycle
  ├─ _apply_train_delay_disruption() with safeguards
  └─ _apply_capacity_reduction_disruption()
  ↓
validate_state_integrity() → validation_result
  ├─ Check negative delays
  ├─ Check capacity violations
  └─ Check time-travel
  ↓
Generate predictions
  ↓
Run optimization
  ↓
Persist results
```

## Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `conflict_injection_probability` | 0.15 | 15% chance per cycle |
| `max_delay_increment_per_cycle` | 5.0 | Max +5 min per cycle |
| `max_total_delay_per_train` | 60.0 | Max 60 min total delay |
| `random_seed` | None | For deterministic testing |

## Testing Recommendations

1. **Deterministic Testing**: Use `random_seed=42` for reproducible tests
2. **Boundary Testing**: Test at delay caps (60 min total, 5 min increment)
3. **Validation Testing**: Inject invalid states and verify validation catches them
4. **Probabilistic Testing**: Run multiple cycles to verify ~15% injection rate
5. **Horizon Testing**: Verify only trains within horizon are affected

## Migration Notes

### Breaking Changes
- `SimulationOrchestrator.__init__()` now accepts `random_seed` parameter
- `_apply_current_disruptions()` signature changed from `() -> None` to `(state_snapshot: Dict) -> Optional[Dict]`

### Backward Compatibility
- `random_seed` is optional (defaults to None)
- Existing code calling `SimulationOrchestrator()` without `random_seed` will work unchanged
