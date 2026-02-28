import React, { createContext, useContext, useState, useEffect } from 'react';
import { Train, Section, Conflict, Platform, OptimizationRun } from '../types';
import { MOCK_TRAINS, MOCK_SECTIONS, MOCK_CONFLICTS, MOCK_PLATFORMS, MOCK_RUNS } from '../data/mockData';

interface LiveData {
  trains: Train[];
  sections: Section[];
  conflicts: Conflict[];
  platforms: Platform[];
  runs: OptimizationRun[];
}

const LiveDataContext = createContext<LiveData | null>(null);

export function LiveDataProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<LiveData>({
    trains: MOCK_TRAINS,
    sections: MOCK_SECTIONS,
    conflicts: MOCK_CONFLICTS,
    platforms: MOCK_PLATFORMS,
    runs: MOCK_RUNS,
  });

  useEffect(() => {
    // Simulate real-time updates every 3 seconds
    const interval = setInterval(() => {
      setData(prev => {
        // Randomly fluctuate delays
        const newTrains = prev.trains.map(t => ({
          ...t,
          predictedDelayMinutes: Math.max(0, t.predictedDelayMinutes + Math.floor(Math.random() * 3) - 1)
        }));
        
        // Randomly fluctuate congestion probabilities
        const newSections = prev.sections.map(s => {
          const newProb = Math.min(1, Math.max(0, s.congestionProbability + (Math.random() * 0.1 - 0.05)));
          return {
            ...s,
            congestionProbability: newProb,
            status: newProb > 0.8 ? 'congested' : (newProb > 0.95 ? 'blocked' : 'clear') as Section['status']
          };
        });

        return { ...prev, trains: newTrains, sections: newSections };
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return <LiveDataContext.Provider value={data}>{children}</LiveDataContext.Provider>;
}

export function useLiveData() {
  const context = useContext(LiveDataContext);
  if (!context) throw new Error('useLiveData must be used within a LiveDataProvider');
  return context;
}
