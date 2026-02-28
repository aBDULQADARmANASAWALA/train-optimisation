"""
Explanation generation for optimization results.

Converts raw CP-SAT solver outputs into human-readable explanations
with conflict details, precedence decisions, and comparative metrics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def generate_explanation(
    solver,
    variables: Dict[str, Any],
    snapshot,
    relevant_stops: List,
    adjusted_timings: Dict[UUID, List[Dict[str, Any]]],
    total_weighted_delay: float,
) -> Dict[str, Any]:
    """
    Generate structured, human-readable explanation of optimization results.
    
    Args:
        solver: CP-SAT solver with solution
        variables: Decision variables from optimization
        snapshot: OptimizationSnapshot with input data
        relevant_stops: List of TrainStop objects in optimization window
        adjusted_timings: Optimized schedule per train
        total_weighted_delay: Total weighted delay from solution
        
    Returns:
        Dictionary with:
        - conflicts_detected: List of conflicts found
        - decisions_made: List of precedence decisions
        - objective_improvement: Before/after comparison
        - train_actions: Per-train actions and reasons
    """
    try:
        precedence_vars = variables.get("precedence_vars", {})
        horizon_start = variables["horizon_start"]
        
        # 1. Detect conflicts (section capacity, headway violations)
        conflicts_detected = _detect_conflicts(
            snapshot,
            relevant_stops,
            precedence_vars,
            solver,
        )
        
        # 2. Extract precedence decisions (which train yielded to which)
        decisions_made = _extract_precedence_decisions(
            precedence_vars,
            solver,
            snapshot,
            relevant_stops,
            variables,
        )
        
        # 3. Calculate objective improvement
        naive_delay = _calculate_naive_delay(snapshot, relevant_stops, horizon_start)
        objective_improvement = {
            "previous_weighted_delay": round(naive_delay, 2),
            "optimized_weighted_delay": round(total_weighted_delay, 2),
            "delay_reduction": round(naive_delay - total_weighted_delay, 2),
            "improvement_percent": round(
                ((naive_delay - total_weighted_delay) / max(naive_delay, 1)) * 100, 1
            ) if naive_delay > 0 else 0.0,
        }
        
        # 4. Generate per-train actions
        train_actions = _generate_train_actions(
            adjusted_timings,
            snapshot,
            relevant_stops,
            decisions_made,
        )
        
        logger.info(
            f"Generated explanation: {len(conflicts_detected)} conflicts, "
            f"{len(decisions_made)} decisions, {len(train_actions)} train actions"
        )
        
        return {
            "conflicts_detected": conflicts_detected,
            "decisions_made": decisions_made,
            "objective_improvement": objective_improvement,
            "train_actions": train_actions,
        }
        
    except Exception as e:
        logger.error(f"Failed to generate explanation: {str(e)}", exc_info=True)
        return {
            "conflicts_detected": [],
            "decisions_made": [],
            "objective_improvement": {},
            "train_actions": [],
            "error": str(e),
        }


def _detect_conflicts(
    snapshot,
    relevant_stops: List,
    precedence_vars: Dict,
    solver,
) -> List[Dict[str, Any]]:
    """
    Detect conflicts that required resolution.
    
    Returns list of conflicts with section name, overlapping trains,
    and time windows.
    """
    conflicts = []
    
    # Group trains by section to find potential conflicts
    section_trains = {}
    train_stops_map = {}
    
    for stop in relevant_stops:
        train_stops_map.setdefault(stop.train_id, []).append(stop)
    
    for train_id, stops_list in train_stops_map.items():
        stops_list.sort(key=lambda s: s.stop_order)
        for i in range(len(stops_list) - 1):
            from_station = stops_list[i].station_id
            to_station = stops_list[i + 1].station_id
            
            # Find section
            section = None
            for sec in snapshot.sections:
                if sec.from_station_id == from_station and sec.to_station_id == to_station:
                    section = sec
                    break
            
            if section:
                section_key = (from_station, to_station)
                if section_key not in section_trains:
                    section_trains[section_key] = {
                        "section": section,
                        "trains": [],
                        "from_station_name": stops_list[i].station_name,
                        "to_station_name": stops_list[i + 1].station_name,
                    }
                
                section_trains[section_key]["trains"].append({
                    "train_id": train_id,
                    "train_number": snapshot.trains.get(train_id, {}).get("train_number", "UNKNOWN"),
                    "departure_stop": stops_list[i],
                    "arrival_stop": stops_list[i + 1],
                })
    
    # Identify conflicts where multiple trains compete for same section
    for section_key, section_data in section_trains.items():
        trains = section_data["trains"]
        if len(trains) > 1:
            section = section_data["section"]
            
            # Check if this section had a precedence decision
            had_precedence = False
            for (train_i, train_j, sec_id), prec_var in precedence_vars.items():
                try:
                    if solver.Value(prec_var) in [0, 1]:
                        had_precedence = True
                        break
                except:
                    pass
            
            if had_precedence or len(trains) > section.capacity:
                conflicts.append({
                    "type": "section_capacity" if len(trains) > section.capacity else "headway_conflict",
                    "section_name": f"{section_data['from_station_name']}–{section_data['to_station_name']}",
                    "section_id": str(section.section_id),
                    "capacity": section.capacity,
                    "competing_trains": len(trains),
                    "train_numbers": [t["train_number"] for t in trains],
                    "headway_required_minutes": section.headway_minutes,
                })
    
    return conflicts


def _extract_precedence_decisions(
    precedence_vars: Dict,
    solver,
    snapshot,
    relevant_stops: List,
    variables: Dict = None,
) -> List[Dict[str, Any]]:
    """
    Extract precedence decisions from solver and convert to human-readable explanations.
    
    Returns list of decisions with:
    - which train yielded
    - which train got priority
    - section name
    - textual explanation
    - estimated delay impact
    """
    decisions = []
    
    # Build train number lookup
    train_numbers = {
        train_id: info.get("train_number", str(train_id)[:8])
        for train_id, info in snapshot.trains.items()
    }
    
    # Build section name lookup
    section_names = {}
    for stop in relevant_stops:
        for sec in snapshot.sections:
            if sec.section_id not in section_names:
                # Find station names for this section
                from_station_name = None
                to_station_name = None
                for s in relevant_stops:
                    if s.station_id == sec.from_station_id:
                        from_station_name = s.station_name
                    if s.station_id == sec.to_station_id:
                        to_station_name = s.station_name
                
                if from_station_name and to_station_name:
                    section_names[sec.section_id] = f"{from_station_name}–{to_station_name}"
    
    for (train_i, train_j, section_id), prec_var in precedence_vars.items():
        try:
            val = solver.Value(prec_var)
            
            if val == 1:
                # train_i got priority, train_j yielded
                priority_train = train_i
                yielded_train = train_j
            elif val == 0:
                # train_j got priority, train_i yielded
                priority_train = train_j
                yielded_train = train_i
            else:
                continue
            
            priority_number = train_numbers.get(priority_train, str(priority_train)[:8])
            yielded_number = train_numbers.get(yielded_train, str(yielded_train)[:8])
            section_name = section_names.get(section_id, f"Section {str(section_id)[:8]}")
            
            # Find section for headway info
            section = None
            for sec in snapshot.sections:
                if sec.section_id == section_id:
                    section = sec
                    break
            
            headway = section.headway_minutes if section else 5.0
            
            # Get delay impact if departure times are present
            delay_impact = 0.0
            from_station_name = section_name.split('–')[0] if '–' in section_name else "station"
            departure_times = variables.get("departure_times", {}) if variables else {}
            
            if departure_times:
                for stop in relevant_stops:
                    if stop.train_id == yielded_train and stop.station_name == from_station_name:
                        stop_id = (stop.train_id, stop.station_id, stop.stop_order)
                        if stop_id in departure_times:
                            try:
                                actual_dep = solver.Value(departure_times[stop_id])
                                sched_dep = int((stop.scheduled_departure - variables["horizon_start"]).total_seconds() / 60)
                                delay_impact = max(0.0, actual_dep - sched_dep)
                            except Exception:
                                pass
                        break
            
            problem = f"Conflict detected on {section_name}"
            solution = f"Train {yielded_number} yielded to Train {priority_number}"
            impact = f"Held for {max(delay_impact, headway):.1f} mins due to headway enforcement"
            
            explanation_text = f"Problem: {problem}\nSolution: {solution}\nImpact: {impact}"
            
            decisions.append({
                "section_name": section_name,
                "priority_train": priority_number,
                "yielded_train": yielded_number,
                "minutes_held": round(max(delay_impact, headway), 2),
                "reason": "headway enforcement / priority weight",
                "delay_impact": round(max(delay_impact, headway), 2),
                "explanation": explanation_text,
                "priority_train_id": str(priority_train),
                "yielded_train_id": str(yielded_train),
                "section_id": str(section_id),
                "action": "hold",
                "headway_minutes": headway,
            })
            
        except Exception as e:
            logger.debug(f"Could not extract precedence for {train_i}/{train_j}: {e}")
            continue
    
    return decisions


def _calculate_naive_delay(snapshot, relevant_stops: List, horizon_start: datetime) -> float:
    """
    Calculate total weighted delay if no optimization was applied.
    
    Uses predicted delays from ML model as baseline.
    """
    naive_delay = 0.0
    
    for stop in relevant_stops:
        train_id = stop.train_id
        predicted_delay = snapshot.predicted_delays.get(train_id, 0.0)
        train_priority = snapshot.trains.get(train_id, {}).get("priority_weight", 1.0)
        
        # Naive delay = predicted delay * priority
        naive_delay += train_priority * max(0, predicted_delay)
    
    return naive_delay


def _generate_train_actions(
    adjusted_timings: Dict[UUID, List[Dict[str, Any]]],
    snapshot,
    relevant_stops: List,
    decisions_made: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Generate per-train action summaries.
    
    Returns list of train actions with:
    - train_id, train_number
    - action (hold/proceed/expedite)
    - reason
    - delay_change
    """
    actions = []
    
    # Build decision lookup by train
    train_decisions = {}
    for decision in decisions_made:
        yielded_id = decision["yielded_train_id"]
        priority_id = decision["priority_train_id"]
        
        if yielded_id not in train_decisions:
            train_decisions[yielded_id] = []
        train_decisions[yielded_id].append({
            "action": "held",
            "reason": decision["explanation"],
        })
        
        if priority_id not in train_decisions:
            train_decisions[priority_id] = []
        train_decisions[priority_id].append({
            "action": "given_priority",
            "reason": f"Proceeded through {decision['section_name']}",
        })
    
    for train_id, timings in adjusted_timings.items():
        if not timings:
            continue
        
        train_info = snapshot.trains.get(train_id, {})
        train_number = train_info.get("train_number", str(train_id)[:8])
        
        # Calculate average delay change
        total_delay = sum(t.get("delay_minutes", 0) for t in timings)
        avg_delay = total_delay / len(timings) if timings else 0
        
        predicted_delay = snapshot.predicted_delays.get(train_id, 0.0)
        delay_change = avg_delay - predicted_delay
        
        # Determine action
        if train_id in train_decisions:
            # Had precedence decision
            decision_info = train_decisions[train_id][0]
            action = decision_info["action"]
            reason = decision_info["reason"]
        elif avg_delay > 5:
            action = "delayed"
            reason = f"Accumulated {avg_delay:.1f}min delay due to network congestion"
        elif avg_delay < 1:
            action = "on_time"
            reason = "Proceeding on schedule"
        else:
            action = "minor_delay"
            reason = f"Minor {avg_delay:.1f}min delay, within tolerance"
        
        actions.append({
            "train_id": str(train_id),
            "train_number": train_number,
            "action": action,
            "reason": reason,
            "delay_change": round(delay_change, 2),
            "final_delay_minutes": round(avg_delay, 2),
            "stops_adjusted": len(timings),
        })
    
    return actions
