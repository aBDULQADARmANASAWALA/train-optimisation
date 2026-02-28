import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { runOptimization } from '../../services/api';
import type { OptimizationResult as ApiOptimizationResult } from '../../app/slices/optimizationSlice';

// OptimizationConfig – kept in sync with app/slices/optimizationSlice
export interface OptimizationConfig {
    constraints?: Record<string, unknown>;
    priority?: 'speed' | 'capacity' | 'efficiency';
    timeHorizon?: number;
}

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface PrecedenceDecision {
    fromTrainId: string;
    toTrainId: string;
    reason: string;
    priority: number;
}

export interface OptimizedScheduleEntry {
    trainId: string;
    originalDeparture: number; // timestamp
    optimizedDeparture: number; // timestamp
    originalArrival: number; // timestamp
    optimizedArrival: number; // timestamp
    delayReduction: number; // minutes
}

export interface OptimizationMetrics {
    objectiveValue: number;
    totalWeightedDelay: number; // minutes
    solverRuntime: number; // milliseconds
    iterationsCompleted: number;
    solutionQuality: number; // 0-1 score
}

export interface OptimizationResult {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    startTime: number; // timestamp
    endTime?: number; // timestamp
    metrics: OptimizationMetrics;
    optimizedSchedule: OptimizedScheduleEntry[];
    precedenceDecisions: PrecedenceDecision[];
    config: OptimizationConfig;
    error?: string;
}

// ============================================================================
// Normalized State Structure
// ============================================================================

export interface OptimizationSliceState {
    // Current optimization run
    currentRun: OptimizationResult | null;

    // Historical runs
    runHistory: Record<string, OptimizationResult>;

    // Metrics from latest run
    latestMetrics: OptimizationMetrics | null;

    // Optimized schedule cache
    optimizedSchedule: OptimizedScheduleEntry[];

    // Precedence decisions
    precedenceDecisions: PrecedenceDecision[];

    // UI state
    isRunning: boolean;
    lastRunTimestamp: number | null;
    loading: boolean;
    error: string | null;

    // Performance tracking
    averageSolverRuntime: number | null;
    bestObjectiveValue: number | null;
}

const initialState: OptimizationSliceState = {
    currentRun: null,
    runHistory: {},
    latestMetrics: null,
    optimizedSchedule: [],
    precedenceDecisions: [],
    isRunning: false,
    lastRunTimestamp: null,
    loading: false,
    error: null,
    averageSolverRuntime: null,
    bestObjectiveValue: null,
};

// ============================================================================
// Async Thunks
// ============================================================================

/**
 * Trigger optimization run with configuration
 */
export const triggerOptimization = createAsyncThunk(
    'optimization/trigger',
    async (config: OptimizationConfig, { rejectWithValue }) => {
        try {
            // Cast to API-level type that has `improvements` and `recommendations`
            const result = await runOptimization(config) as unknown as ApiOptimizationResult;
            // Transform API response to our domain model
            return {
                id: result.id,
                status: result.status,
                startTime: Date.now(),
                metrics: {
                    objectiveValue: result.improvements.efficiencyScore,
                    totalWeightedDelay: result.improvements.timeReduction,
                    solverRuntime: 0,
                    iterationsCompleted: 0,
                    solutionQuality: result.improvements.efficiencyScore,
                },
                optimizedSchedule: [],
                precedenceDecisions: result.recommendations.map((rec: { trainId: string; action: string; impact: string; }) => ({
                    fromTrainId: rec.trainId,
                    toTrainId: rec.trainId,
                    reason: rec.action,
                    priority: 1,
                })),
                config,
            };
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to run optimization';
            return rejectWithValue(message);
        }
    }
);

// ============================================================================
// Redux Slice
// ============================================================================

const optimizationSlice = createSlice({
    name: 'optimization',
    initialState,
    reducers: {
        // Manual state updates
        setOptimizedSchedule: (state, action: PayloadAction<OptimizedScheduleEntry[]>) => {
            state.optimizedSchedule = action.payload;
        },

        setPrecedenceDecisions: (state, action: PayloadAction<PrecedenceDecision[]>) => {
            state.precedenceDecisions = action.payload;
        },

        addPrecedenceDecision: (state, action: PayloadAction<PrecedenceDecision>) => {
            state.precedenceDecisions.push(action.payload);
        },

        removePrecedenceDecision: (
            state,
            action: PayloadAction<{ fromTrainId: string; toTrainId: string; }>
        ) => {
            const { fromTrainId, toTrainId } = action.payload;
            state.precedenceDecisions = state.precedenceDecisions.filter(
                (pd) => !(pd.fromTrainId === fromTrainId && pd.toTrainId === toTrainId)
            );
        },

        clearOptimization: (state) => {
            state.currentRun = null;
            state.optimizedSchedule = [];
            state.precedenceDecisions = [];
            state.latestMetrics = null;
            state.isRunning = false;
            state.error = null;
        },

        clearHistory: (state) => {
            state.runHistory = {};
            state.lastRunTimestamp = null;
            state.averageSolverRuntime = null;
            state.bestObjectiveValue = null;
        },
    },

    extraReducers: (builder) => {
        builder
            .addCase(triggerOptimization.pending, (state) => {
                state.isRunning = true;
                state.loading = true;
                state.error = null;
                state.currentRun = {
                    id: `run-${Date.now()}`,
                    status: 'running',
                    startTime: Date.now(),
                    metrics: {
                        objectiveValue: 0,
                        totalWeightedDelay: 0,
                        solverRuntime: 0,
                        iterationsCompleted: 0,
                        solutionQuality: 0,
                    },
                    optimizedSchedule: [],
                    precedenceDecisions: [],
                    config: {},
                };
            })
            .addCase(triggerOptimization.fulfilled, (state, action) => {
                const result = action.payload as OptimizationResult;
                result.endTime = Date.now();
                result.status = 'completed';

                // Calculate runtime
                result.metrics.solverRuntime = result.endTime - result.startTime;

                // Store current run
                state.currentRun = result;
                state.runHistory[result.id] = result;

                // Update metrics
                state.latestMetrics = result.metrics;
                state.optimizedSchedule = result.optimizedSchedule;
                state.precedenceDecisions = result.precedenceDecisions;

                // Track performance
                state.lastRunTimestamp = result.endTime;

                // Update best objective value
                if (
                    state.bestObjectiveValue === null ||
                    result.metrics.objectiveValue > state.bestObjectiveValue
                ) {
                    state.bestObjectiveValue = result.metrics.objectiveValue;
                }

                // Update average solver runtime
                const runtimes = Object.values(state.runHistory).map((r) => r.metrics.solverRuntime);
                state.averageSolverRuntime =
                    runtimes.reduce((a, b) => a + b, 0) / Math.max(runtimes.length, 1);

                state.isRunning = false;
                state.loading = false;
            })
            .addCase(triggerOptimization.rejected, (state, action) => {
                state.isRunning = false;
                state.loading = false;
                state.error = action.payload as string;
                if (state.currentRun) {
                    state.currentRun.status = 'failed';
                    state.currentRun.error = action.payload as string;
                }
            });
    },
});

export const {
    setOptimizedSchedule,
    setPrecedenceDecisions,
    addPrecedenceDecision,
    removePrecedenceDecision,
    clearOptimization,
    clearHistory,
} = optimizationSlice.actions;

// ============================================================================
// Selectors
// ============================================================================

// Current run selectors
export const selectCurrentRun = (state: RootState) => state.optimization.currentRun;
export const selectCurrentRunStatus = (state: RootState) => state.optimization.currentRun?.status;
export const selectIsOptimizationRunning = (state: RootState) => state.optimization.isRunning;

// Metrics selectors
export const selectLatestMetrics = (state: RootState) => state.optimization.latestMetrics;
export const selectObjectiveValue = (state: RootState) =>
    state.optimization.latestMetrics?.objectiveValue ?? 0;
export const selectTotalWeightedDelay = (state: RootState) =>
    state.optimization.latestMetrics?.totalWeightedDelay ?? 0;
export const selectSolverRuntime = (state: RootState) =>
    state.optimization.latestMetrics?.solverRuntime ?? 0;
export const selectSolutionQuality = (state: RootState) =>
    state.optimization.latestMetrics?.solutionQuality ?? 0;

// Schedule and decisions selectors
export const selectOptimizedSchedule = (state: RootState) => state.optimization.optimizedSchedule;
export const selectPrecedenceDecisions = (state: RootState) =>
    state.optimization.precedenceDecisions;

/**
 * Select optimized schedule for specific train
 */
export const selectTrainOptimization = (trainId: string) => (state: RootState) =>
    state.optimization.optimizedSchedule.find((entry) => entry.trainId === trainId);

/**
 * Select average delay reduction across all trains
 */
export const selectAverageDelayReduction = (state: RootState) => {
    const schedule = state.optimization.optimizedSchedule;
    if (schedule.length === 0) return 0;
    const totalReduction = schedule.reduce((sum, entry) => sum + entry.delayReduction, 0);
    return Math.round((totalReduction / schedule.length) * 100) / 100;
};

// History selectors
export const selectRunHistory = (state: RootState) => Object.values(state.optimization.runHistory);
export const selectRunById = (runId: string) => (state: RootState) =>
    state.optimization.runHistory[runId];
export const selectRunCount = (state: RootState) => Object.keys(state.optimization.runHistory).length;

// Performance selectors
export const selectLastRunTimestamp = (state: RootState) => state.optimization.lastRunTimestamp;
export const selectAverageSolverRuntime = (state: RootState) =>
    state.optimization.averageSolverRuntime;
export const selectBestObjectiveValue = (state: RootState) =>
    state.optimization.bestObjectiveValue;

// State selectors
export const selectOptimizationLoading = (state: RootState) => state.optimization.loading;
export const selectOptimizationError = (state: RootState) => state.optimization.error;

/**
 * Select improvement summary
 */
export const selectImprovementSummary = (state: RootState) => ({
    objectiveValue: state.optimization.latestMetrics?.objectiveValue ?? 0,
    totalWeightedDelay: state.optimization.latestMetrics?.totalWeightedDelay ?? 0,
    solverRuntime: state.optimization.latestMetrics?.solverRuntime ?? 0,
    solutionQuality: state.optimization.latestMetrics?.solutionQuality ?? 0,
    affectedTrains: state.optimization.optimizedSchedule.length,
    averageDelayReduction: selectAverageDelayReduction(state),
    priorityConstraints: state.optimization.precedenceDecisions.length,
});

export default optimizationSlice.reducer;
