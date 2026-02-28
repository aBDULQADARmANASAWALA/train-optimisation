import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { fetchLiveState } from '../../services/api';

// ============================================================================
// API Response Types
// ============================================================================

export interface LiveState {
    trains: Record<string, {
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
    }>;
    signals: Record<string, unknown>;
    trackSections: Record<string, {
        id: string;
        name: string;
        occupancy: number;
        maxCapacity: number;
        status: string;
    }>;
    timestamp: number;
    isConnected: boolean;
}

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface Station {
    id: string;
    name: string;
    location: {
        lat: number;
        lng: number;
    };
    platforms: number;
    capacity: number;
}

export interface Section {
    id: string;
    name: string;
    fromStationId: string;
    toStationId: string;
    length: number; // in km
    speedLimit: number; // km/h
    trackType: 'single' | 'double' | 'multiple';
    occupiedTrackCount: number;
}

export interface Train {
    id: string;
    name: string;
    status: 'on-time' | 'delayed' | 'at-station' | 'departed' | 'cancelled';
    currentLocationId: string; // station or section id
    currentLocationName: string;
    scheduledDeparture: number; // timestamp
    actualDeparture?: number;
    estimatedArrival: number; // timestamp
    destination: string;
    destinationId: string;
    passengers: number;
    capacity: number;
    platform?: string;
    delayMinutes: number;
}

export interface TrainState {
    trainId: string;
    status: 'on-time' | 'delayed' | 'at-station' | 'departed' | 'cancelled';
    delayMinutes: number;
    passengers: number;
    occupancyRate: number;
}

export interface Conflict {
    id: string;
    trainIds: string[];
    sectionId: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    estimatedResolutionTime: number; // timestamp
    description: string;
}

export interface CongestionData {
    sectionId: string;
    occupancyRate: number;
    trainCount: number;
}

// ============================================================================
// Normalized State Structure
// ============================================================================

export interface StateSliceState {
    // Normalized entities
    entities: {
        stationsById: Record<string, Station>;
        sectionsById: Record<string, Section>;
        trainsById: Record<string, Train>;
    };

    // Domain data
    conflicts: Record<string, Conflict>;
    sectionLoad: Record<string, CongestionData>;

    // UI state
    loading: boolean;
    error: string | null;
    lastUpdated: number | null;
}

const initialState: StateSliceState = {
    entities: {
        stationsById: {},
        sectionsById: {},
        trainsById: {},
    },
    conflicts: {},
    sectionLoad: {},
    loading: false,
    error: null,
    lastUpdated: null,
};

// ============================================================================
// Async Thunks
// ============================================================================

/**
 * Load live state from API and normalize into Redux store
 */
export const loadLiveState = createAsyncThunk(
    'state/loadLiveState',
    async (_, { rejectWithValue }) => {
        try {
            const liveState = await fetchLiveState();
            return liveState;
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to load live state';
            return rejectWithValue(message);
        }
    }
);

// ============================================================================
// Redux Slice
// ============================================================================

const stateSlice = createSlice({
    name: 'state',
    initialState,
    reducers: {
        // Manual state updates
        addStation: (state, action: PayloadAction<Station>) => {
            state.entities.stationsById[action.payload.id] = action.payload;
        },

        addSection: (state, action: PayloadAction<Section>) => {
            state.entities.sectionsById[action.payload.id] = action.payload;
        },

        updateTrain: (state, action: PayloadAction<Train>) => {
            state.entities.trainsById[action.payload.id] = action.payload;
        },

        updateSectionCongestion: (state, action: PayloadAction<CongestionData>) => {
            state.sectionLoad[action.payload.sectionId] = action.payload;
        },

        addConflict: (state, action: PayloadAction<Conflict>) => {
            state.conflicts[action.payload.id] = action.payload;
        },

        removeConflict: (state, action: PayloadAction<string>) => {
            delete state.conflicts[action.payload];
        },

        clearState: (state) => {
            state.entities = initialState.entities;
            state.conflicts = {};
            state.sectionLoad = {};
            state.lastUpdated = null;
            state.error = null;
        },
    },

    extraReducers: (builder) => {
        builder
            .addCase(loadLiveState.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(loadLiveState.fulfilled, (state, action) => {
                // Normalize incoming data into entities
                const liveState = action.payload;

                // Populate stations
                if (liveState.trains) {
                    // Extract unique stations from trains
                    const stationMap = new Map<string, Station>();
                    Object.values(liveState.trains).forEach((train) => {
                        if (!stationMap.has(train.currentLocation)) {
                            stationMap.set(train.currentLocation, {
                                id: train.currentLocation,
                                name: train.currentLocation,
                                location: { lat: 0, lng: 0 }, // Will come from API
                                platforms: 2,
                                capacity: 1000,
                            });
                        }
                    });
                    stationMap.forEach((station) => {
                        state.entities.stationsById[station.id] = station;
                    });
                }

                // Populate trains
                if (liveState.trains) {
                    Object.entries(liveState.trains).forEach(([trainId, train]) => {
                        state.entities.trainsById[trainId] = {
                            id: trainId,
                            name: train.name,
                            status: train.status,
                            currentLocationId: train.currentLocation,
                            currentLocationName: train.currentLocation,
                            scheduledDeparture: new Date(train.scheduledDeparture).getTime(),
                            actualDeparture: train.actualDeparture ? new Date(train.actualDeparture).getTime() : undefined,
                            estimatedArrival: new Date(train.estimatedArrival).getTime(),
                            destination: train.destination,
                            destinationId: `${train.destination}-id`,
                            passengers: train.passengers,
                            capacity: train.capacity,
                            platform: train.platform,
                            delayMinutes: 0,
                        };
                    });
                }

                // Populate track sections
                if (liveState.trackSections) {
                    Object.entries(liveState.trackSections).forEach(([sectionId, section]) => {
                        state.entities.sectionsById[sectionId] = {
                            id: sectionId,
                            name: section.name,
                            fromStationId: 'unknown',
                            toStationId: 'unknown',
                            length: 10,
                            speedLimit: 160,
                            trackType: 'double',
                            occupiedTrackCount: section.occupancy,
                        };

                        // Calculate congestion
                        const occupancyRate = section.maxCapacity > 0 ? section.occupancy / section.maxCapacity : 0;
                        state.sectionLoad[sectionId] = {
                            sectionId,
                            occupancyRate,
                            trainCount: Math.round(section.occupancy),
                        };
                    });
                }

                state.loading = false;
                state.lastUpdated = Date.now();
            })
            .addCase(loadLiveState.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });
    },
});

export const {
    addStation,
    addSection,
    updateTrain,
    updateSectionCongestion,
    addConflict,
    removeConflict,
    clearState,
} = stateSlice.actions;

// ============================================================================
// Selectors
// ============================================================================

// Entity selectors
export const selectStationsById = (state: RootState) => state.state.entities.stationsById;
export const selectSectionsById = (state: RootState) => state.state.entities.sectionsById;
export const selectTrainsById = (state: RootState) => state.state.entities.trainsById;

// Derived selectors
export const selectAllStations = (state: RootState) =>
    Object.values(state.state.entities.stationsById);

export const selectAllSections = (state: RootState) =>
    Object.values(state.state.entities.sectionsById);

export const selectAllTrains = (state: RootState) =>
    Object.values(state.state.entities.trainsById);

/**
 * Select trains with conflicts or delays
 */
export const selectConflictedTrains = (state: RootState) => {
    const trains = Object.values(state.state.entities.trainsById);
    const conflictTrainIds = new Set<string>();

    Object.values(state.state.conflicts).forEach((conflict) => {
        conflict.trainIds.forEach((trainId) => conflictTrainIds.add(trainId));
    });

    return trains.filter((train) => conflictTrainIds.has(train.id) || train.status === 'delayed');
};

/**
 * Select sections with high congestion (>70% occupancy)
 */
export const selectHighCongestionSections = (state: RootState) => {
    const sections = Object.values(state.state.entities.sectionsById);
    const congestionThreshold = 0.7;

    return sections.filter((section) => {
        const congestion = state.state.sectionLoad[section.id];
        return congestion && congestion.occupancyRate > congestionThreshold;
    });
};

/**
 * Select conflicts by severity
 */
export const selectConflictsBySeverity = (severity: Conflict['severity']) => (state: RootState) =>
    Object.values(state.state.conflicts).filter((conflict) => conflict.severity === severity);

/**
 * Select specific train by ID
 */
export const selectTrainById = (trainId: string) => (state: RootState) =>
    state.state.entities.trainsById[trainId];

/**
 * Select specific station by ID
 */
export const selectStationById = (stationId: string) => (state: RootState) =>
    state.state.entities.stationsById[stationId];

/**
 * Select specific section by ID
 */
export const selectSectionById = (sectionId: string) => (state: RootState) =>
    state.state.entities.sectionsById[sectionId];

// State selectors
export const selectStateLoading = (state: RootState) => state.state.loading;
export const selectStateError = (state: RootState) => state.state.error;
export const selectLastUpdated = (state: RootState) => state.state.lastUpdated;

/**
 * Select all conflicts
 */
export const selectAllConflicts = (state: RootState) => Object.values(state.state.conflicts);

/**
 * Select system statistics
 */
export const selectSystemStats = (state: RootState) => {
    const trains = Object.values(state.state.entities.trainsById);
    const sections = Object.values(state.state.entities.sectionsById);

    const delayedTrains = trains.filter((t) => t.status === 'delayed').length;
    const avgOccupancy =
        Object.values(state.state.sectionLoad).reduce((sum, c) => sum + c.occupancyRate, 0) /
        Math.max(Object.keys(state.state.sectionLoad).length, 1);

    return {
        totalTrains: trains.length,
        totalSections: sections.length,
        delayedTrains,
        conflicts: Object.keys(state.state.conflicts).length,
        avgSectionOccupancy: Math.round(avgOccupancy * 100),
    };
};

export default stateSlice.reducer;
