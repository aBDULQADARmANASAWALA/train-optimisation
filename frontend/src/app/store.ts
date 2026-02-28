import { configureStore } from '@reduxjs/toolkit';
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import stateSlice from '../features/state/stateSlice';
import optimizationSlice from '../features/optimization/optimizationSlice';
import kpiSlice from '../features/kpi/kpiSlice';
import overrideSlice from '../features/override/overrideSlice';

export const store = configureStore({
    reducer: {
        state: stateSlice,
        optimization: optimizationSlice,
        kpi: kpiSlice,
        override: overrideSlice,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                ignoredActions: ['state/setLiveState', 'kpi/setMetrics'],
                ignoredActionPaths: ['payload.timestamp'],
                ignoredPaths: ['state.lastUpdated', 'kpi.lastFetch'],
            },
        }).concat(),
    devTools: process.env.NODE_ENV !== 'production',
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Export typed hooks for use throughout the app
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
