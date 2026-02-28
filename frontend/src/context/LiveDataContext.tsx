import React, { createContext, useContext, useState, useEffect } from 'react';
import { Train, Section, Conflict, Platform, OptimizationRun, KPIDashboard } from '../types';
import { api } from '../api';

interface LiveData {
  trains: Train[];
  sections: Section[];
  conflicts: Conflict[];
  platforms: Platform[];
  runs: OptimizationRun[];
  metrics: KPIDashboard | null;
  loading: boolean;
  error: string | null;
  refreshData: () => Promise<void>;
}

const LiveDataContext = createContext<LiveData | null>(null);

export function LiveDataProvider({ children }: { children: React.ReactNode; }) {
  const [data, setData] = useState<{
    trains: Train[];
    sections: Section[];
    conflicts: Conflict[];
    platforms: Platform[];
    runs: OptimizationRun[];
    metrics: KPIDashboard | null;
  }>(() => {
    const cached = localStorage.getItem('railOrchestraCache');
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        console.error('Failed to parse cached data', e);
      }
    }
    return {
      trains: [],
      sections: [],
      conflicts: [],
      platforms: [],
      runs: [],
      metrics: null,
    };
  });

  const [loading, setLoading] = useState(() => {
    return !localStorage.getItem('railOrchestraCache');
  });
  const [error, setError] = useState<string | null>(null);

  const refreshData = async () => {
    try {
      const liveState = await api.getLiveState();
      const history = await api.getOptimizationHistory();
      const metrics = await api.getMetrics();

      const newData = {
        trains: liveState.trains,
        sections: liveState.sections,
        conflicts: liveState.conflicts,
        platforms: liveState.platforms,
        runs: history,
        metrics: metrics,
      };

      setData(newData);
      try {
        localStorage.setItem('railOrchestraCache', JSON.stringify(newData));
      } catch (e) {
        console.warn('Failed to save to localStorage', e);
      }
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch live data:', err);
      setError(err.message || 'Failed to connect to backend API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData();
    // Refresh every 5 seconds for live state
    const interval = setInterval(refreshData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <LiveDataContext.Provider value={{ ...data, loading, error, refreshData }}>
      {children}
    </LiveDataContext.Provider>
  );
}

export function useLiveData() {
  const context = useContext(LiveDataContext);
  if (!context) throw new Error('useLiveData must be used within a LiveDataProvider');
  return context;
}
