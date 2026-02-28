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

type DataState = {
  trains: Train[];
  sections: Section[];
  conflicts: Conflict[];
  platforms: Platform[];
  runs: OptimizationRun[];
  metrics: KPIDashboard | null;
};

const EMPTY_STATE: DataState = {
  trains: [],
  sections: [],
  conflicts: [],
  platforms: [],
  runs: [],
  metrics: null,
};

function loadCache(): DataState {
  try {
    const cached = localStorage.getItem('railOrchestraCache');
    if (cached) return JSON.parse(cached);
  } catch (e) {
    console.warn('Failed to parse cache', e);
  }
  return EMPTY_STATE;
}

export function LiveDataProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<DataState>(loadCache);
  const [loading, setLoading] = useState(() => !localStorage.getItem('railOrchestraCache'));
  const [error, setError] = useState<string | null>(null);

  const refreshData = async () => {
    // Fire all three requests in parallel — allSettled means a single failure
    // never blocks the others (e.g. /history 500 won't prevent live state update)
    const [liveResult, historyResult, metricsResult] = await Promise.allSettled([
      api.getLiveState(),
      api.getOptimizationHistory(),
      api.getMetrics(),
    ]);

    setData(prev => {
      const next = { ...prev };
      let changed = false;

      if (liveResult.status === 'fulfilled') {
        next.trains = liveResult.value.trains;
        next.sections = liveResult.value.sections;
        next.conflicts = liveResult.value.conflicts;
        next.platforms = liveResult.value.platforms;
        changed = true;
      } else {
        console.warn('[refresh] getLiveState failed:', (liveResult.reason as Error)?.message);
      }

      if (historyResult.status === 'fulfilled') {
        next.runs = historyResult.value;
        changed = true;
      } else {
        console.warn('[refresh] getOptimizationHistory failed:', (historyResult.reason as Error)?.message);
      }

      if (metricsResult.status === 'fulfilled') {
        next.metrics = metricsResult.value;
        changed = true;
      } else {
        console.warn('[refresh] getMetrics failed:', (metricsResult.reason as Error)?.message);
      }

      if (changed) {
        try { localStorage.setItem('railOrchestraCache', JSON.stringify(next)); } catch { }
      }

      return next;
    });

    // Clear error if at least live state succeeded
    if (liveResult.status === 'fulfilled') {
      setError(null);
    } else {
      setError('Could not reach backend API');
    }

    setLoading(false);
  };

  useEffect(() => {
    refreshData();
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
