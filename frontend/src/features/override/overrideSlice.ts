import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { sendOverrideDecision } from '../../services/api';
import type { OverrideRequest, Override } from '../../app/slices/overrideSlice';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface SelectedTrain {
    trainId: string;
    trainName: string;
    currentLocation: string;
    status: string;
}

export interface OverrideAction {
    id: string;
    trainId: string;
    type: 'platform-change' | 'delay-extension' | 'priority-boost' | 'cancellation';
    originalValue: string | number;
    newValue: string | number;
    reason: string;
    expiryTime?: number;
}

export interface OverrideSubmission {
    actions: OverrideAction[];
    batchId: string;
    submittedAt: number;
    appliedBy: string;
}

// ============================================================================
// Normalized State Structure
// ============================================================================

export interface OverrideSliceState {
    // Selected trains for override
    selectedTrains: Record<string, SelectedTrain>;
    selectedTrainIds: string[];

    // Pending override actions
    pendingActions: Record<string, OverrideAction>;

    // Submitted overrides tracking
    submissions: Record<string, OverrideSubmission>;
    currentSubmissionId: string | null;

    // API responses
    appliedOverrides: Record<string, Override>;

    // UI state
    isSubmitting: boolean;
    loading: boolean;
    error: string | null;
    success: boolean;
    successMessage: string | null;
    lastSubmittedAt: number | null;
}

const initialState: OverrideSliceState = {
    selectedTrains: {},
    selectedTrainIds: [],
    pendingActions: {},
    submissions: {},
    currentSubmissionId: null,
    appliedOverrides: {},
    isSubmitting: false,
    loading: false,
    error: null,
    success: false,
    successMessage: null,
    lastSubmittedAt: null,
};

// ============================================================================
// Async Thunks
// ============================================================================

/**
 * Submit override decisions to backend
 */
export const submitOverride = createAsyncThunk(
    'override/submit',
    async (
        action: OverrideAction,
        { rejectWithValue }
    ) => {
        try {
            const request: OverrideRequest = {
                trainId: action.trainId,
                type: action.type,
                newValue: action.newValue,
                reason: action.reason,
                expiryTime: action.expiryTime,
            };

            const result = await sendOverrideDecision(request);
            return result;
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to submit override';
            return rejectWithValue(message);
        }
    }
);

// ============================================================================
// Redux Slice
// ============================================================================

const overrideSlice = createSlice({
    name: 'override',
    initialState,
    reducers: {
        // Train selection
        addSelectedTrain: (state, action: PayloadAction<SelectedTrain>) => {
            const trainId = action.payload.trainId;
            state.selectedTrains[trainId] = action.payload;
            if (!state.selectedTrainIds.includes(trainId)) {
                state.selectedTrainIds.push(trainId);
            }
        },

        removeSelectedTrain: (state, action: PayloadAction<string>) => {
            const trainId = action.payload;
            delete state.selectedTrains[trainId];
            state.selectedTrainIds = state.selectedTrainIds.filter((id) => id !== trainId);
        },

        clearSelectedTrains: (state) => {
            state.selectedTrains = {};
            state.selectedTrainIds = [];
        },

        // Override action management
        addOverrideAction: (state, action: PayloadAction<OverrideAction>) => {
            state.pendingActions[action.payload.id] = action.payload;
        },

        updateOverrideAction: (state, action: PayloadAction<OverrideAction>) => {
            state.pendingActions[action.payload.id] = action.payload;
        },

        removeOverrideAction: (state, action: PayloadAction<string>) => {
            delete state.pendingActions[action.payload];
        },

        clearPendingActions: (state) => {
            state.pendingActions = {};
        },

        // UI state management
        resetOverrideState: (state) => {
            state.selectedTrains = {};
            state.selectedTrainIds = [];
            state.pendingActions = {};
            state.error = null;
            state.success = false;
            state.successMessage = null;
            state.isSubmitting = false;
        },

        clearSuccess: (state) => {
            state.success = false;
            state.successMessage = null;
        },

        clearError: (state) => {
            state.error = null;
        },

        setAppliedBy: (state, action: PayloadAction<string>) => {
            // Update all pending actions with applied by
            Object.values(state.pendingActions).forEach((action_item) => {
                // Note: Cannot modify appliedBy directly, it's part of submission context
            });
        },
    },

    extraReducers: (builder) => {
        builder
            .addCase(submitOverride.pending, (state) => {
                state.isSubmitting = true;
                state.loading = true;
                state.error = null;
                state.success = false;
            })
            .addCase(submitOverride.fulfilled, (state, action) => {
                const override = action.payload;

                // Store applied override
                state.appliedOverrides[override.id] = override;

                // Create submission record
                const submissionId = `submission-${Date.now()}`;
                state.submissions[submissionId] = {
                    actions: Object.values(state.pendingActions),
                    batchId: submissionId,
                    submittedAt: Date.now(),
                    appliedBy: 'system', // Will be set by middleware
                };
                state.currentSubmissionId = submissionId;

                // Update UI state
                state.isSubmitting = false;
                state.loading = false;
                state.success = true;
                state.successMessage = `Override applied successfully for ${override.trainId}`;
                state.lastSubmittedAt = Date.now();

                // Clear pending actions after successful submission
                state.pendingActions = {};
            })
            .addCase(submitOverride.rejected, (state, action) => {
                state.isSubmitting = false;
                state.loading = false;
                state.error = action.payload as string;
                state.success = false;
            });
    },
});

export const {
    addSelectedTrain,
    removeSelectedTrain,
    clearSelectedTrains,
    addOverrideAction,
    updateOverrideAction,
    removeOverrideAction,
    clearPendingActions,
    resetOverrideState,
    clearSuccess,
    clearError,
    setAppliedBy,
} = overrideSlice.actions;

// ============================================================================
// Selectors
// ============================================================================

// Selected trains selectors
export const selectSelectedTrains = (state: RootState) =>
    Object.values(state.override.selectedTrains);
export const selectSelectedTrainIds = (state: RootState) => state.override.selectedTrainIds;
export const selectSelectedTrainCount = (state: RootState) => state.override.selectedTrainIds.length;

/**
 * Select specific selected train
 */
export const selectSelectedTrainById = (trainId: string) => (state: RootState) =>
    state.override.selectedTrains[trainId];

/**
 * Check if train is selected
 */
export const selectIsTrainSelected = (trainId: string) => (state: RootState) =>
    state.override.selectedTrainIds.includes(trainId);

// Override actions selectors
export const selectPendingOverrideActions = (state: RootState) =>
    Object.values(state.override.pendingActions);
export const selectPendingActionCount = (state: RootState) =>
    Object.keys(state.override.pendingActions).length;

/**
 * Select specific pending action
 */
export const selectPendingActionById = (actionId: string) => (state: RootState) =>
    state.override.pendingActions[actionId];

/**
 * Select all actions for a specific train
 */
export const selectActionsByTrain = (trainId: string) => (state: RootState) =>
    Object.values(state.override.pendingActions).filter((action) => action.trainId === trainId);

// Applied overrides selectors
export const selectAppliedOverrides = (state: RootState) =>
    Object.values(state.override.appliedOverrides);

/**
 * Select applied overrides for specific train
 */
export const selectAppliedOverridesByTrain = (trainId: string) => (state: RootState) =>
    Object.values(state.override.appliedOverrides).filter((override) => override.trainId === trainId);

// Submission history selectors
export const selectSubmissionHistory = (state: RootState) =>
    Object.values(state.override.submissions);

/**
 * Select specific submission
 */
export const selectSubmissionById = (submissionId: string) => (state: RootState) =>
    state.override.submissions[submissionId];

export const selectCurrentSubmission = (state: RootState) =>
    state.override.currentSubmissionId ? state.override.submissions[state.override.currentSubmissionId] : null;

// UI state selectors
export const selectOverrideLoading = (state: RootState) => state.override.loading;
export const selectOverrideSubmitting = (state: RootState) => state.override.isSubmitting;
export const selectOverrideError = (state: RootState) => state.override.error;
export const selectOverrideSuccess = (state: RootState) => state.override.success;
export const selectOverrideSuccessMessage = (state: RootState) => state.override.successMessage;
export const selectLastSubmittedAt = (state: RootState) => state.override.lastSubmittedAt;

/**
 * Select override form readiness
 */
export const selectCanSubmitOverride = (state: RootState) =>
    state.override.selectedTrainIds.length > 0 &&
    Object.keys(state.override.pendingActions).length > 0 &&
    !state.override.isSubmitting;

/**
 * Select summary for override dialog
 */
export const selectOverrideSummary = (state: RootState) => ({
    selectedCount: state.override.selectedTrainIds.length,
    actionCount: Object.keys(state.override.pendingActions).length,
    isSubmitting: state.override.isSubmitting,
    canSubmit: selectCanSubmitOverride(state),
    error: state.override.error,
    success: state.override.success,
    successMessage: state.override.successMessage,
});

export default overrideSlice.reducer;
