import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { Train, Section, Conflict, Platform, OptimizationRun, KPIDashboard, OptimizationPlan } from '../types';
import { api } from '../api';

interface LiveData {
  trains: Train[];
  sections: Section[];
  conflicts: Conflict[];
  platforms: Platform[];
  runs: OptimizationRun[];
  metrics: KPIDashboard | null;
  plan: OptimizationPlan | null;
  loading: boolean;
  error: string | null;
  refreshData: (forceShowLoading?: boolean) => Promise<void>;
}

const LiveDataContext = createContext<LiveData | null>(null);

type DataState = {
  trains: Train[];
  sections: Section[];
  conflicts: Conflict[];
  platforms: Platform[];
  runs: OptimizationRun[];
  metrics: KPIDashboard | null;
  plan: OptimizationPlan | null;
};

const EMPTY_STATE: DataState = {
  trains: [],
  sections: [],
  conflicts: [],
  platforms: [],
  runs: [],
  metrics: null,
  plan: null,
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
  const refreshInFlight = useRef(false);

  const refreshData = async (forceShowLoading: boolean = false) => {
    if (forceShowLoading) setLoading(true);
    // Guard: skip if a previous refresh is still in-flight unless we are forcing
    if (refreshInFlight.current && !forceShowLoading) return;
    refreshInFlight.current = true;
    try {
      const [liveResult, historyResult, metricsResult, planResult] = await Promise.allSettled([
        api.getLiveState(),
        api.getOptimizationHistory(),
        api.getMetrics(),
        api.getOptimizationPlan(),
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

        if (planResult.status === 'fulfilled') {
          next.plan = planResult.value;
          changed = true;
        } else {
          console.warn('[refresh] getOptimizationPlan failed:', (planResult.reason as Error)?.message);
        }

        if (changed) {
          try { localStorage.setItem('railOrchestraCache', JSON.stringify(next)); } catch { }
        }

        return next;
      });

      if (liveResult.status === 'fulfilled') {
        setError(null);
      } else {
        setError('Could not reach backend API');
      }

      setLoading(false);
    } finally {
      refreshInFlight.current = false;
    }
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
