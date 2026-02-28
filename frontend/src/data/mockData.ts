import { Train, Section, Platform, OptimizationRun, Conflict } from '../types';

export const MOCK_TRAINS: Train[] = [
  { id: 'T-101', name: 'Express Blue', type: 'express', currentSection: 'S-12', priorityWeight: 10, predictedDelayMinutes: 0, status: 'on_time' },
  { id: 'T-204', name: 'Passenger Local', type: 'passenger', currentSection: 'S-14', priorityWeight: 5, predictedDelayMinutes: 12, status: 'delayed' },
  { id: 'T-305', name: 'Freight Heavy', type: 'freight', currentSection: 'S-08', priorityWeight: 2, predictedDelayMinutes: 45, status: 'delayed' },
  { id: 'T-102', name: 'Express Red', type: 'express', currentSection: 'S-22', priorityWeight: 10, predictedDelayMinutes: 2, status: 'on_time' },
  { id: 'T-205', name: 'Passenger Regional', type: 'passenger', currentSection: 'S-18', priorityWeight: 6, predictedDelayMinutes: 0, status: 'on_time' },
  { id: 'T-306', name: 'Freight Cargo', type: 'freight', currentSection: 'S-03', priorityWeight: 2, predictedDelayMinutes: 0, status: 'on_time' },
];

export const MOCK_SECTIONS: Section[] = [
  { id: 'S-12', name: 'North Corridor A', capacity: 2, currentOccupancy: 1, congestionProbability: 0.1, status: 'clear' },
  { id: 'S-14', name: 'North Corridor B', capacity: 2, currentOccupancy: 2, congestionProbability: 0.85, status: 'congested' },
  { id: 'S-08', name: 'East Junction', capacity: 1, currentOccupancy: 1, congestionProbability: 0.95, status: 'congested' },
  { id: 'S-22', name: 'West Valley', capacity: 3, currentOccupancy: 1, congestionProbability: 0.05, status: 'clear' },
  { id: 'S-18', name: 'South Approach', capacity: 2, currentOccupancy: 1, congestionProbability: 0.3, status: 'clear' },
  { id: 'S-03', name: 'Industrial Spur', capacity: 1, currentOccupancy: 1, congestionProbability: 0.1, status: 'clear' },
];

export const MOCK_PLATFORMS: Platform[] = [
  { id: 'P-1', stationName: 'Central Station', platformNumber: '1', isOccupied: true, occupyingTrainId: 'T-101' },
  { id: 'P-2', stationName: 'Central Station', platformNumber: '2', isOccupied: false },
  { id: 'P-3', stationName: 'North Terminal', platformNumber: '1', isOccupied: true, occupyingTrainId: 'T-204' },
  { id: 'P-4', stationName: 'South Station', platformNumber: '1', isOccupied: false },
];

export const MOCK_RUNS: OptimizationRun[] = [
  { id: 'OPT-001', timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), totalDelayReduced: 45, conflictsResolved: 3, status: 'success' },
  { id: 'OPT-002', timestamp: new Date(Date.now() - 1000 * 60 * 10).toISOString(), totalDelayReduced: 30, conflictsResolved: 2, status: 'success' },
  { id: 'OPT-003', timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), totalDelayReduced: 0, conflictsResolved: 0, status: 'success' },
  { id: 'OPT-004', timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(), totalDelayReduced: 120, conflictsResolved: 5, status: 'success' },
];

export const MOCK_CONFLICTS: Conflict[] = [
  { id: 'C-001', type: 'headway', location: 'S-14', trainsInvolved: ['T-204', 'T-101'], severity: 'high', resolved: false },
  { id: 'C-002', type: 'capacity', location: 'S-08', trainsInvolved: ['T-305', 'T-205'], severity: 'medium', resolved: true },
];
