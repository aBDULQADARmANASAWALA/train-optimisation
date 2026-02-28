export type TrainType = 'express' | 'passenger' | 'freight';

export interface Train {
  id: string;
  name: string;
  type: TrainType;
  currentSection: string;
  priorityWeight: number;
  predictedDelayMinutes: number;
  status: 'on_time' | 'delayed' | 'stopped';
}

export interface Section {
  id: string;
  name: string;
  capacity: number;
  currentOccupancy: number;
  congestionProbability: number;
  status: 'clear' | 'congested' | 'blocked';
}

export interface Platform {
  id: string;
  stationName: string;
  platformNumber: string;
  isOccupied: boolean;
  occupyingTrainId?: string;
}

export interface OptimizationRun {
  id: string;
  timestamp: string;
  totalDelayReduced: number;
  conflictsResolved: number;
  status: 'success' | 'failed' | 'overridden';
}

export interface Conflict {
  id: string;
  type: 'headway' | 'capacity' | 'platform';
  location: string;
  trainsInvolved: string[];
  severity: 'high' | 'medium' | 'low';
  resolved: boolean;
}

export interface NetworkState {
  timestamp: string;
  active_trains: number;
  total_trains: number;
  sections_occupied: number;
  total_sections: number;
  average_section_utilization: number;
  current_conflicts: number;
  trains: Train[];
  sections: Section[];
  platforms: Platform[];
  conflicts: Conflict[];
}

export interface KPIDashboard {
  timestamp: string;
  cycle_number: number;
  total_weighted_delay_minutes: number;
  average_section_utilization_percent: number;
  conflicts_detected: number;
  conflicts_avoided: number;
  trains_delayed: number;
  trains_on_time: number;
  optimization_runtime_seconds: number;
  schedule_adherence_percent: number;
  prediction_accuracy_mae: number;
}

export interface OptimizationPlanStop {
  station_name: string;
  stop_order: number;
  scheduled_arrival: string | null;
  adjusted_arrival: string | null;
  delay_minutes: number;
}

export interface OptimizationPlanEntry {
  train_id: string;
  train_number: string;
  action: 'on_time' | 'minor_delay' | 'hold';
  max_delay_minutes: number;
  stops: OptimizationPlanStop[];
}

export interface ConflictDetected {
  type: string;
  section_name: string;
  section_id: string;
  capacity: number;
  competing_trains: number;
  train_numbers: string[];
  headway_required_minutes: number;
}

export interface DecisionMade {
  priority_train: string;
  priority_train_id: string;
  yielded_train: string;
  yielded_train_id: string;
  section_name: string;
  section_id: string;
  action: string;
  reason: string;
  explanation: string;
  headway_minutes: number;
}

export interface ObjectiveImprovement {
  previous_weighted_delay: number;
  optimized_weighted_delay: number;
  delay_reduction: number;
  improvement_percent: number;
}

export interface TrainAction {
  train_id: string;
  train_number: string;
  action: string;
  reason: string;
  delay_change: number;
  final_delay_minutes: number;
  stops_adjusted: number;
}

export interface OptimizationExplanation {
  conflicts_detected: ConflictDetected[];
  decisions_made: DecisionMade[];
  objective_improvement: ObjectiveImprovement;
  train_actions: TrainAction[];
}

export interface OptimizationPlan {
  available: boolean;
  message?: string;
  timestamp: string | null;
  total_weighted_delay: number;
  solver_runtime_seconds?: number;
  plan: OptimizationPlanEntry[];
  explanation?: OptimizationExplanation;
}
