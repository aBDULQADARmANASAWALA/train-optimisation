import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '../store';
import api from '../../services/api';

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

export interface KPITimeSeries {
    timestamp: number;
    value: number;
}

export interface KPIData {
    metrics: Record<string, KPIMetric>;
    timeSeries: Record<string, KPITimeSeries[]>;
    aggregations: {
        onTimePercentage: number;
        averageDelay: number;
        capacityUtilization: number;
        systemEfficiency: number;
    };
}

interface KPISliceState {
    data: KPIData;
    loading: boolean;
    error: string | null;
    lastFetch: number | null;
    refreshInterval: number;
}

const initialState: KPISliceState = {
    data: {
        metrics: {},
        timeSeries: {},
        aggregations: {
            onTimePercentage: 0,
            averageDelay: 0,
            capacityUtilization: 0,
            systemEfficiency: 0,
        },
    },
    loading: false,
    error: null,
    lastFetch: null,
    refreshInterval: 30000, // 30 seconds
};

// Async thunk for fetching metrics
export const fetchMetrics = createAsyncThunk(
    'kpi/fetchMetrics',
    async (_, { rejectWithValue }) => {
        try {
            const response = await api.get<KPIData>('/metrics');
            return response.data;
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch metrics');
        }
    }
);

const kpiSlice = createSlice({
    name: 'kpi',
    initialState,
    reducers: {
        setKPIData: (state, action: PayloadAction<KPIData>) => {
            state.data = action.payload;
            state.lastFetch = Date.now();
            state.error = null;
        },
        updateMetric: (state, action: PayloadAction<KPIMetric>) => {
            state.data.metrics[action.payload.id] = action.payload;
        },
        updateTimeSeries: (
            state,
            action: PayloadAction<{ metricId: string; data: KPITimeSeries[]; }>
        ) => {
            state.data.timeSeries[action.payload.metricId] = action.payload.data;
        },
        setRefreshInterval: (state, action: PayloadAction<number>) => {
            state.refreshInterval = action.payload;
        },
        clearKPIData: (state) => {
            state.data = initialState.data;
            state.lastFetch = null;
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchMetrics.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchMetrics.fulfilled, (state, action) => {
                state.data = action.payload;
                state.loading = false;
                state.lastFetch = Date.now();
            })
            .addCase(fetchMetrics.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });
    },
});

export const {
    setKPIData,
    updateMetric,
    updateTimeSeries,
    setRefreshInterval,
    clearKPIData,
} = kpiSlice.actions;

// Selectors — NOTE: the store uses features/kpi/kpiSlice reducer.
// state.kpi reflects KPISliceState from that file (current, metricsById, history…).
export const selectKPIData = (state: RootState) => state.kpi.current;
export const selectKPIMetrics = (state: RootState) => Object.values(state.kpi.metricsById);
export const selectMetricById = (metricId: string) => (state: RootState) =>
    state.kpi.metricsById[metricId];
export const selectKPIAggregations = (state: RootState) => state.kpi.current;
export const selectTimeSeriesData = (_metricId: string) => (state: RootState) =>
    state.kpi.history;
export const selectKPILoading = (state: RootState) => state.kpi.loading;
export const selectKPIError = (state: RootState) => state.kpi.error;
export const selectRefreshInterval = (state: RootState) => state.kpi.refreshInterval;

export default kpiSlice.reducer;
