import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { RootState } from '../store';

export interface Train {
    id: string;
    name: string;
    status: 'on-time' | 'delayed' | 'at-station' | 'departed';
    currentLocation: string;
    scheduledDeparture: string;
    actualDeparture?: string;
    destination: string;
    passengers: number;
    capacity: number;
    estimatedArrival: string;
    platform?: string;
}

export interface SignalState {
    id: string;
    status: 'green' | 'yellow' | 'red';
    location: string;
}

export interface TrackSection {
    id: string;
    name: string;
    occupancy: number;
    maxCapacity: number;
    status: 'free' | 'occupied' | 'congested';
}

export interface LiveState {
    trains: Record<string, Train>;
    signals: Record<string, SignalState>;
    trackSections: Record<string, TrackSection>;
    timestamp: number;
    isConnected: boolean;
}

interface StateSliceState {
    live: LiveState;
    loading: boolean;
    error: string | null;
    lastUpdated: number | null;
}

const initialState: StateSliceState = {
    live: {
        trains: {},
        signals: {},
        trackSections: {},
        timestamp: 0,
        isConnected: false,
    },
    loading: false,
    error: null,
    lastUpdated: null,
};

const stateSlice = createSlice({
    name: 'state',
    initialState,
    reducers: {
        setLiveState: (state, action: PayloadAction<LiveState>) => {
            state.live = action.payload;
            state.lastUpdated = Date.now();
            state.error = null;
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.loading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
            state.loading = false;
        },
        updateTrain: (state, action: PayloadAction<{ trainId: string; train: Train; }>) => {
            const { trainId, train } = action.payload;
            state.live.trains[trainId] = train;
            state.lastUpdated = Date.now();
        },
        setConnected: (state, action: PayloadAction<boolean>) => {
            state.live.isConnected = action.payload;
        },
        clearState: (state) => {
            state.live = initialState.live;
            state.lastUpdated = null;
            state.error = null;
        },
    },
});

export const {
    setLiveState,
    setLoading,
    setError,
    updateTrain,
    setConnected,
    clearState,
} = stateSlice.actions;

// Selectors — NOTE: the store uses features/state/stateSlice reducer.
// state.state reflects StateSliceState from that file (entities, conflicts, sectionLoad…)
export const selectLiveState = (state: RootState) => state.state.entities;
export const selectAllTrains = (state: RootState) =>
    Object.values(state.state.entities.trainsById);
export const selectTrainById = (trainId: string) => (state: RootState) =>
    state.state.entities.trainsById[trainId];
export const selectAllSignals = (_state: RootState): unknown[] => [];
export const selectAllTrackSections = (state: RootState) =>
    Object.values(state.state.entities.sectionsById);
export const selectStateLoading = (state: RootState) => state.state.loading;
export const selectStateError = (state: RootState) => state.state.error;
export const selectIsConnected = (_state: RootState) => true;

export default stateSlice.reducer;
