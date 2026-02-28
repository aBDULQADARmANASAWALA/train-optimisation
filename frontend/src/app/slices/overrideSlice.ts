import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '../store';
import api from '../../services/api';

export interface Override {
    id: string;
    trainId: string;
    type: 'platform-change' | 'delay-extension' | 'priority-boost' | 'cancellation';
    originalValue: string | number;
    newValue: string | number;
    reason: string;
    appliedBy: string;
    appliedAt: number;
    expiresAt?: number;
    status: 'active' | 'expired' | 'revoked';
}

export interface OverrideRequest {
    trainId: string;
    type: Override['type'];
    newValue: string | number;
    reason: string;
    expiryTime?: number;
}

interface OverrideSliceState {
    overrides: Record<string, Override>;
    activeOverrides: string[];
    loading: boolean;
    error: string | null;
    lastAppliedAt: number | null;
}

const initialState: OverrideSliceState = {
    overrides: {},
    activeOverrides: [],
    loading: false,
    error: null,
    lastAppliedAt: null,
};

// Async thunk for applying overrides
export const applyOverride = createAsyncThunk(
    'override/apply',
    async (request: OverrideRequest, { rejectWithValue }) => {
        try {
            const response = await api.post<Override>('/override', request);
            return response.data;
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Failed to apply override');
        }
    }
);

const overrideSlice = createSlice({
    name: 'override',
    initialState,
    reducers: {
        addOverride: (state, action: PayloadAction<Override>) => {
            const override = action.payload;
            state.overrides[override.id] = override;
            if (!state.activeOverrides.includes(override.id) && override.status === 'active') {
                state.activeOverrides.push(override.id);
            }
        },
        removeOverride: (state, action: PayloadAction<string>) => {
            const overrideId = action.payload;
            if (state.overrides[overrideId]) {
                state.overrides[overrideId].status = 'revoked';
                state.activeOverrides = state.activeOverrides.filter((id) => id !== overrideId);
            }
        },
        expireOverride: (state, action: PayloadAction<string>) => {
            const overrideId = action.payload;
            if (state.overrides[overrideId]) {
                state.overrides[overrideId].status = 'expired';
                state.activeOverrides = state.activeOverrides.filter((id) => id !== overrideId);
            }
        },
        refreshActiveOverrides: (state) => {
            const now = Date.now();
            state.activeOverrides = state.activeOverrides.filter((id) => {
                const override = state.overrides[id];
                if (!override) return false;
                if (override.expiresAt && override.expiresAt < now) {
                    override.status = 'expired';
                    return false;
                }
                return override.status === 'active';
            });
        },
        clearOverrides: (state) => {
            state.overrides = {};
            state.activeOverrides = [];
            state.lastAppliedAt = null;
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(applyOverride.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(applyOverride.fulfilled, (state, action) => {
                const override = action.payload;
                state.overrides[override.id] = override;
                if (override.status === 'active') {
                    state.activeOverrides.push(override.id);
                }
                state.loading = false;
                state.lastAppliedAt = Date.now();
            })
            .addCase(applyOverride.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });
    },
});

export const {
    addOverride,
    removeOverride,
    expireOverride,
    refreshActiveOverrides,
    clearOverrides,
} = overrideSlice.actions;

// Selectors — NOTE: the store uses features/override/overrideSlice reducer,
// so state.override reflects OverrideSliceState from that file.
export const selectAllOverrides = (state: RootState) =>
    Object.values(state.override.appliedOverrides);
export const selectActiveOverrides = (state: RootState) =>
    Object.values(state.override.appliedOverrides);
export const selectOverridesByTrain = (trainId: string) => (state: RootState) =>
    Object.values(state.override.appliedOverrides).filter(
        (o: Override) => o.trainId === trainId
    );
export const selectOverrideById = (overrideId: string) => (state: RootState) =>
    state.override.appliedOverrides[overrideId];
export const selectOverrideLoading = (state: RootState) => state.override.loading;
export const selectOverrideError = (state: RootState) => state.override.error;
export const selectActiveOverrideCount = (state: RootState) =>
    Object.keys(state.override.appliedOverrides).length;

export default overrideSlice.reducer;
