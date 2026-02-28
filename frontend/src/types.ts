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
