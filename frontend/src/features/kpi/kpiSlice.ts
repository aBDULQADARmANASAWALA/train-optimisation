import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { fetchKPIs } from '../../services/api';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface KPIMetric {
    id: string;
    name: string;
    value: number;
    unit: string;
    threshold?: {
        warning: number;
        critical: number;
    };
    trend?: 'up' | 'down' | 'stable';
    trendPercent?: number;
    timestamp: number;
}

export interface KPISnapshot {
    timestamp: number;
    totalWeightedDelay: number; // minutes
    averageDelay: number; // minutes
    throughput: number; // trains per hour
    sectionUtilization: number; // percentage 0-100
    onTimePercentage: number; // percentage 0-100
    capacityUtilization: number; // percentage 0-100
    systemEfficiency: number; // 0-1 score
}

export interface KPIHistoryEntry extends KPISnapshot {
    id: string;
}

export interface KPIData {
    current: KPISnapshot;
    metrics: Record<string, KPIMetric>;
    history: KPIHistoryEntry[];
}

// ============================================================================
// Normalized State Structure
// ============================================================================

export interface KPISliceState {
    // Current KPI values
    current: KPISnapshot | null;

    // All KPI metrics
    metricsById: Record<string, KPIMetric>;

    // Historical KPI snapshots for charting
    history: KPIHistoryEntry[];
    maxHistorySize: number; // Keep last N entries for memory efficiency

    // WebSocket connection state
    wsConnected: boolean;
    wsConnectAttempts: number;

    // UI state
    loading: boolean;
    error: string | null;
    lastUpdated: number | null;
    refreshInterval: number; // milliseconds
}

const initialState: KPISliceState = {
    current: null,
    metricsById: {},
    history: [],
    maxHistorySize: 3600, // Store 1 hour at 1-second intervals, or 60 entries at 1-minute intervals
    wsConnected: false,
    wsConnectAttempts: 0,
    loading: false,
    error: null,
    lastUpdated: null,
    refreshInterval: 30000, // 30 seconds default
};

// ============================================================================
// Async Thunks
// ============================================================================

/**
 * Load KPI data from API
 */
export const loadKPIs = createAsyncThunk(
    'kpi/load',
    async (_, { rejectWithValue }) => {
        try {
            const kpiData = await fetchKPIs();
            return kpiData;
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to load KPI data';
            return rejectWithValue(message);
        }
    }
);

// ============================================================================
// Redux Slice
// ============================================================================

const kpiSlice = createSlice({
    name: 'kpi',
    initialState,
    reducers: {
        // Manual KPI updates (for WebSocket or real-time data)
        updateKPISnapshot: (state, action: PayloadAction<KPISnapshot>) => {
            state.current = action.payload;
            state.lastUpdated = Date.now();
            state.error = null;

            // Add to history
            const historyEntry: KPIHistoryEntry = {
                id: `kpi-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                ...action.payload,
            };
            state.history.push(historyEntry);

            // Trim history if exceeds max size
            if (state.history.length > state.maxHistorySize) {
                state.history = state.history.slice(-state.maxHistorySize);
            }
        },

        updateMetric: (state, action: PayloadAction<KPIMetric>) => {
            state.metricsById[action.payload.id] = action.payload;
        },

        setRefreshInterval: (state, action: PayloadAction<number>) => {
            state.refreshInterval = action.payload;
        },

        // WebSocket state management
        setWSConnected: (state, action: PayloadAction<boolean>) => {
            state.wsConnected = action.payload;
            if (action.payload) {
                state.wsConnectAttempts = 0;
            } else {
                state.wsConnectAttempts += 1;
            }
        },

        resetWSAttempts: (state) => {
            state.wsConnectAttempts = 0;
        },

        clearHistory: (state) => {
            state.history = [];
            state.current = null;
            state.lastUpdated = null;
        },

        setMaxHistorySize: (state, action: PayloadAction<number>) => {
            state.maxHistorySize = action.payload;
            // Trim if necessary
            if (state.history.length > action.payload) {
                state.history = state.history.slice(-action.payload);
            }
        },
    },

    extraReducers: (builder) => {
        builder
            .addCase(loadKPIs.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(loadKPIs.fulfilled, (state, action) => {
                const kpiData = action.payload;

                // Update current values from the KPIData.current snapshot
                if (kpiData.current) {
                    state.current = kpiData.current;

                    // Add to history
                    const historyEntry: KPIHistoryEntry = {
                        id: `kpi-${Date.now()}`,
                        ...kpiData.current,
                    };
                    state.history.push(historyEntry);

                    // Trim history
                    if (state.history.length > state.maxHistorySize) {
                        state.history = state.history.slice(-state.maxHistorySize);
                    }
                }

                // Store metrics
                if (kpiData.metrics) {
                    Object.entries(kpiData.metrics).forEach(([metricId, metric]) => {
                        state.metricsById[metricId] = metric;
                    });
                }

                state.loading = false;
                state.lastUpdated = Date.now();
            })
            .addCase(loadKPIs.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });
    },
});

export const {
    updateKPISnapshot,
    updateMetric,
    setRefreshInterval,
    setWSConnected,
    resetWSAttempts,
    clearHistory,
    setMaxHistorySize,
} = kpiSlice.actions;

// ============================================================================
// Selectors
// ============================================================================

// Current KPI selectors
export const selectCurrentKPI = (state: RootState) => state.kpi.current;
export const selectTotalWeightedDelay = (state: RootState) =>
    state.kpi.current?.totalWeightedDelay ?? 0;
export const selectAverageDelay = (state: RootState) => state.kpi.current?.averageDelay ?? 0;
export const selectThroughput = (state: RootState) => state.kpi.current?.throughput ?? 0;
export const selectSectionUtilization = (state: RootState) =>
    state.kpi.current?.sectionUtilization ?? 0;
export const selectOnTimePercentage = (state: RootState) =>
    state.kpi.current?.onTimePercentage ?? 0;
export const selectCapacityUtilization = (state: RootState) =>
    state.kpi.current?.capacityUtilization ?? 0;
export const selectSystemEfficiency = (state: RootState) =>
    state.kpi.current?.systemEfficiency ?? 0;

/**
 * Select all KPI metrics
 */
export const selectAllMetrics = (state: RootState) => Object.values(state.kpi.metricsById);

/**
 * Select specific metric by ID
 */
export const selectMetricById = (metricId: string) => (state: RootState) =>
    state.kpi.metricsById[metricId];

// Historical data selectors
export const selectKPIHistory = (state: RootState) => state.kpi.history;

/**
 * Select time series data for specific metric
 * Used for Recharts visualization
 */
export const selectKPITimeSeries = (metricKey: keyof KPISnapshot) => (state: RootState) =>
    state.kpi.history.map((entry) => ({
        timestamp: entry.timestamp,
        value: entry[metricKey],
    }));

/**
 * Select last N historical entries
 */
export const selectKPIHistoryLast = (count: number) => (state: RootState) =>
    state.kpi.history.slice(-count);

/**
 * Select KPI statistics (min, max, avg)
 */
export const selectKPIStatistics = (metricKey: keyof KPISnapshot) => (state: RootState) => {
    const values = state.kpi.history.map((entry) => Number(entry[metricKey]));

    if (values.length === 0) {
        return { min: 0, max: 0, avg: 0, latest: 0 };
    }

    return {
        min: Math.min(...values),
        max: Math.max(...values),
        avg: Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100) / 100,
        latest: values[values.length - 1],
    };
};

// WebSocket state selectors
export const selectWSConnected = (state: RootState) => state.kpi.wsConnected;
export const selectWSConnectAttempts = (state: RootState) => state.kpi.wsConnectAttempts;

// UI state selectors
export const selectKPILoading = (state: RootState) => state.kpi.loading;
export const selectKPIError = (state: RootState) => state.kpi.error;
export const selectLastUpdated = (state: RootState) => state.kpi.lastUpdated;
export const selectRefreshInterval = (state: RootState) => state.kpi.refreshInterval;

/**
 * Select complete KPI snapshot for dashboard display
 */
export const selectKPIDashboard = (state: RootState) => ({
    current: state.kpi.current,
    history: state.kpi.history,
    loading: state.kpi.loading,
    error: state.kpi.error,
    wsConnected: state.kpi.wsConnected,
    lastUpdated: state.kpi.lastUpdated,
});

export default kpiSlice.reducer;
