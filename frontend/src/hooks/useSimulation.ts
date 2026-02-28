import { useEffect, useRef, useCallback, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../app/store';
import { loadLiveState } from '../features/state/stateSlice';
import { loadKPIs } from '../features/kpi/kpiSlice';
import { triggerOptimization } from '../features/optimization/optimizationSlice';
import type { OptimizationConfig } from '../app/slices/optimizationSlice';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface UseSimulationOptions {
    enablePolling?: boolean;
    liveStateInterval?: number; // milliseconds
    kpiInterval?: number; // milliseconds
    autoStartOptimization?: boolean;
}

export interface UseSimulationReturn {
    // State
    isLoading: boolean;
    isOptimizing: boolean;
    liveStateLoading: boolean;
    kpiLoading: boolean;

    // Data
    liveStateError: string | null;
    kpiError: string | null;
    optimizationError: string | null;

    // Actions
    loadState: () => Promise<void>;
    loadMetrics: () => Promise<void>;
    runOptimization: (config?: OptimizationConfig) => Promise<void>;
    stopPolling: () => void;
    startPolling: () => void;

    // Polling state
    isPolling: boolean;
}

// ============================================================================
// useSimulation Hook
// ============================================================================

/**
 * Custom hook to manage railway simulation lifecycle
 * Encapsulates data loading, KPI fetching, and optimization triggering
 * Handles polling intervals and cleanup automatically
 */
export const useSimulation = (
    options: UseSimulationOptions = {}
): UseSimulationReturn => {
    const {
        enablePolling = true,
        liveStateInterval = 5000, // 5 seconds
        kpiInterval = 30000, // 30 seconds
        autoStartOptimization = false,
    } = options;

    const dispatch = useAppDispatch();

    // Select loading states from Redux
    const liveStateLoading = useAppSelector((state) => state.state.loading);
    const kpiLoading = useAppSelector((state) => state.kpi.loading);
    const isOptimizing = useAppSelector((state) => state.optimization.isRunning);

    // Select error states
    const liveStateError = useAppSelector((state) => state.state.error);
    const kpiError = useAppSelector((state) => state.kpi.error);
    const optimizationError = useAppSelector((state) => state.optimization.error);

    // Local state
    const [isPolling, setIsPolling] = useState(enablePolling);

    // Interval refs for cleanup
    const liveStateIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const kpiIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // ============================================================================
    // Action Methods
    // ============================================================================

    /**
     * Load live state from API
     */
    const loadState = useCallback(async () => {
        try {
            await dispatch(loadLiveState()).unwrap();
        } catch (error) {
            console.error('Failed to load live state:', error);
        }
    }, [dispatch]);

    /**
     * Load KPI metrics from API
     */
    const loadMetrics = useCallback(async () => {
        try {
            await dispatch(loadKPIs()).unwrap();
        } catch (error) {
            console.error('Failed to load KPI metrics:', error);
        }
    }, [dispatch]);

    /**
     * Trigger optimization run
     */
    const runOptimization = useCallback(
        async (config: OptimizationConfig = {}) => {
            try {
                await dispatch(triggerOptimization(config)).unwrap();
            } catch (error) {
                console.error('Failed to run optimization:', error);
            }
        },
        [dispatch]
    );

    /**
     * Stop all polling
     */
    const stopPolling = useCallback(() => {
        if (liveStateIntervalRef.current) {
            clearInterval(liveStateIntervalRef.current);
            liveStateIntervalRef.current = null;
        }
        if (kpiIntervalRef.current) {
            clearInterval(kpiIntervalRef.current);
            kpiIntervalRef.current = null;
        }
        setIsPolling(false);
    }, []);

    /**
     * Start polling intervals
     */
    const startPolling = useCallback(() => {
        // Stop any existing intervals
        stopPolling();

        // Load initial data immediately
        loadState();
        loadMetrics();

        // Set up live state polling
        liveStateIntervalRef.current = setInterval(() => {
            loadState();
        }, liveStateInterval);

        // Set up KPI polling (slower interval)
        kpiIntervalRef.current = setInterval(() => {
            loadMetrics();
        }, kpiInterval);

        setIsPolling(true);
    }, [loadState, loadMetrics, liveStateInterval, kpiInterval, stopPolling]);

    // ============================================================================
    // Effects
    // ============================================================================

    /**
     * Initialize polling on mount
     */
    useEffect(() => {
        if (enablePolling) {
            startPolling();
        }

        // Auto-start optimization if requested
        if (autoStartOptimization) {
            runOptimization();
        }

        // Cleanup on unmount
        return () => {
            stopPolling();
        };
    }, [enablePolling, startPolling, stopPolling, autoStartOptimization, runOptimization]);

    // ============================================================================
    // Return
    // ============================================================================

    const isLoading = liveStateLoading || kpiLoading;

    return {
        // State
        isLoading,
        isOptimizing,
        liveStateLoading,
        kpiLoading,

        // Data
        liveStateError,
        kpiError,
        optimizationError,

        // Actions
        loadState,
        loadMetrics,
        runOptimization,
        stopPolling,
        startPolling,

        // Polling state
        isPolling,
    };
};

export default useSimulation;
