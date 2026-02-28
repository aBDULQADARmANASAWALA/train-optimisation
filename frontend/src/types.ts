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

export interface OptimizationPlan {
  available: boolean;
  message?: string;
  timestamp: string | null;
  total_weighted_delay: number;
  solver_runtime_seconds?: number;
  plan: OptimizationPlanEntry[];
}
