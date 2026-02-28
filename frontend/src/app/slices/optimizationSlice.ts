import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '../store';
import api from '../../services/api';

export interface OptimizationConfig {
    constraints?: Record<string, unknown>;
    priority?: 'speed' | 'capacity' | 'efficiency';
    timeHorizon?: number;
}

export interface OptimizationResult {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    startTime: number;
    endTime?: number;
    improvements: {
        timeReduction: number;
        capacityGain: number;
        efficiencyScore: number;
    };
    recommendations: Array<{
        trainId: string;
        action: string;
        impact: string;
    }>;
    config: OptimizationConfig;
}

interface OptimizationSliceState {
    runs: Record<string, OptimizationResult>;
    activeRunId: string | null;
    loading: boolean;
    error: string | null;
    lastRunTime: number | null;
}

const initialState: OptimizationSliceState = {
    runs: {},
    activeRunId: null,
    loading: false,
    error: null,
    lastRunTime: null,
};

// Async thunk for running optimization
export const runOptimization = createAsyncThunk(
    'optimization/run',
    async (config: OptimizationConfig, { rejectWithValue }) => {
        try {
            const response = await api.post<OptimizationResult>('/optimization/run', config);
            return response.data;
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Failed to run optimization');
        }
    }
);

const optimizationSlice = createSlice({
    name: 'optimization',
    initialState,
    reducers: {
        clearOptimizations: (state) => {
            state.runs = {};
            state.activeRunId = null;
            state.lastRunTime = null;
            state.error = null;
        },
        setActiveRunId: (state, action: PayloadAction<string | null>) => {
            state.activeRunId = action.payload;
        },
        updateRunStatus: (
            state,
            action: PayloadAction<{ runId: string; status: OptimizationResult['status']; }>
        ) => {
            const { runId, status } = action.payload;
            if (state.runs[runId]) {
                state.runs[runId].status = status;
            }
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(runOptimization.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(runOptimization.fulfilled, (state, action) => {
                const result = action.payload;
                state.runs[result.id] = result;
                state.activeRunId = result.id;
                state.loading = false;
                state.lastRunTime = Date.now();
            })
            .addCase(runOptimization.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });
    },
});

export const { clearOptimizations, setActiveRunId, updateRunStatus } =
    optimizationSlice.actions;

// Selectors — NOTE: the store uses features/optimization/optimizationSlice reducer.
// state.optimization reflects OptimizationSliceState from that file.
export const selectOptimizationRuns = (state: RootState) =>
    Object.values(state.optimization.runHistory);
export const selectActiveRun = (state: RootState) => state.optimization.currentRun;
export const selectOptimizationLoading = (state: RootState) => state.optimization.loading;
export const selectOptimizationError = (state: RootState) => state.optimization.error;
export const selectRunById = (runId: string) => (state: RootState) =>
    state.optimization.runHistory[runId];

export default optimizationSlice.reducer;
