import React, { useCallback, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../app/store';
import useSimulation from '../hooks/useSimulation';

// Import selectors
import { selectAllTrains, selectAllStations, selectAllSections } from '../features/state/stateSlice';
import { selectCurrentKPI, selectKPIHistory } from '../features/kpi/kpiSlice';
import { selectAllConflicts, selectSystemStats } from '../features/state/stateSlice';

// Import components
import MainLayout from '../components/layout/MainLayout';
import RailwayMap from '../components/railway-map/RailwayMap';
import TrainTable from '../components/train-table/TrainTable';
import KPIPanel from '../components/kpi-panel/KPIPanel';

// ============================================================================
// Control Panel Component (placeholder)
// ============================================================================

interface ControlPanelProps {
    onOptimize?: () => void;
    isOptimizing?: boolean;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ onOptimize, isOptimizing = false }) => {
    return (
        <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 shadow-md">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Controls</h3>
            <div className="space-y-3">
                <button
                    onClick={onOptimize}
                    disabled={isOptimizing}
                    className="w-full px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors duration-200"
                >
                    {isOptimizing ? 'Running Optimization...' : 'Run Optimization'}
                </button>
                <button className="w-full px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg transition-colors duration-200">
                    Export Report
                </button>
            </div>
        </div>
    );
};

// ============================================================================
// Dashboard Component
// ============================================================================

export const Dashboard: React.FC = () => {
    const dispatch = useAppDispatch();
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [selectedTrainId, setSelectedTrainId] = useState<string | null>(null);

    // Use simulation hook for polling and initial load
    const {
        isLoading,
        isOptimizing,
        liveStateError,
        kpiError,
        loadState,
        loadMetrics,
        runOptimization,
    } = useSimulation({
        enablePolling: true,
        liveStateInterval: 5000, // 5 seconds for live state
        kpiInterval: 30000, // 30 seconds for KPIs
        autoStartOptimization: false,
    });

    // Select data from Redux store
    const trains = useAppSelector(selectAllTrains);
    const stations = useAppSelector(selectAllStations);
    const sections = useAppSelector(selectAllSections);
    const conflicts = useAppSelector(selectAllConflicts);
    const currentKPI = useAppSelector(selectCurrentKPI);
    const kpiHistory = useAppSelector(selectKPIHistory);
    const systemStats = useAppSelector(selectSystemStats);

    // Build section loads from state
    const sectionLoads = useAppSelector((state) => state.state.sectionLoad);

    // ============================================================================
    // Event Handlers
    // ============================================================================

    const handleOptimize = useCallback(() => {
        runOptimization({
            priority: 'efficiency',
            timeHorizon: 3600, // 1 hour
        });
    }, [runOptimization]);

    const handleStationClick = useCallback((stationId: string) => {
        console.log('Station clicked:', stationId);
        // Could open a modal or sidebar with station details
    }, []);

    const handleSectionClick = useCallback((sectionId: string) => {
        console.log('Section clicked:', sectionId);
        // Could open a modal with section details
    }, []);

    const handleTrainSelect = useCallback((trainId: string) => {
        setSelectedTrainId(trainId);
        console.log('Train selected:', trainId);
        // Could trigger override panel or other actions
    }, []);

    const handleTrainClick = useCallback((train: any) => {
        console.log('Train clicked:', train.id);
        // Could open detailed train view
    }, []);

    const handleToggleSidebar = useCallback(() => {
        setSidebarOpen((prev) => !prev);
    }, []);

    // ============================================================================
    // Determine System Status
    // ============================================================================

    const systemStatus = liveStateError ? 'error' : isLoading ? 'disconnected' : 'connected';

    // ============================================================================
    // Render
    // ============================================================================

    return (
        <MainLayout
            systemStatus={systemStatus}
            onOptimize={handleOptimize}
            sidebarOpen={sidebarOpen}
            onToggleSidebar={handleToggleSidebar}
        >
            {/* Main Content Grid */}
            <div className="w-full h-full overflow-auto">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 auto-rows-max lg:auto-rows-auto min-h-full">
                    {/* Top Row: KPI Panel (full width) */}
                    <div className="lg:col-span-12">
                        <KPIPanel
                            current={currentKPI}
                            history={kpiHistory}
                            loading={isLoading}
                            error={kpiError}
                            onRefresh={loadMetrics}
                        />
                    </div>

                    {/* Middle Section: Railway Map (left) and Control Panel (right) */}
                    <div className="lg:col-span-8">
                        <div className="bg-slate-900 rounded-lg border border-slate-700 shadow-lg overflow-hidden" style={{ height: '600px' }}>
                            <RailwayMap
                                stations={stations}
                                sections={sections}
                                sectionLoads={sectionLoads}
                                conflicts={conflicts}
                                onStationClick={handleStationClick}
                                onSectionClick={handleSectionClick}
                            />
                        </div>
                    </div>

                    {/* Control Panel and Stats (right sidebar) */}
                    <div className="lg:col-span-4 space-y-4">
                        {/* Control Panel */}
                        <ControlPanel onOptimize={handleOptimize} isOptimizing={isOptimizing} />

                        {/* System Stats Card */}
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 shadow-md">
                            <h3 className="text-sm font-semibold text-slate-300 mb-4">System Stats</h3>
                            <div className="space-y-3 text-sm">
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Total Trains</span>
                                    <span className="font-semibold text-cyan-400">{systemStats.totalTrains}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Track Sections</span>
                                    <span className="font-semibold text-cyan-400">{systemStats.totalSections}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Delayed Trains</span>
                                    <span className={`font-semibold ${systemStats.delayedTrains > 0 ? 'text-orange-400' : 'text-green-400'}`}>
                                        {systemStats.delayedTrains}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-400">Active Conflicts</span>
                                    <span className={`font-semibold ${systemStats.conflicts > 0 ? 'text-red-400' : 'text-green-400'}`}>
                                        {systemStats.conflicts}
                                    </span>
                                </div>
                                <div className="border-t border-slate-700 pt-3 mt-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-slate-400">Avg Utilization</span>
                                        <span className="font-semibold text-yellow-400">{systemStats.avgSectionOccupancy}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Status Card */}
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 shadow-md">
                            <h3 className="text-sm font-semibold text-slate-300 mb-3">Connection Status</h3>
                            <div className="space-y-2 text-xs text-slate-400">
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`} />
                                    <span>{isLoading ? 'Loading...' : 'Connected'}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${isOptimizing ? 'bg-cyan-500 animate-pulse' : 'bg-slate-600'}`} />
                                    <span>{isOptimizing ? 'Optimizing...' : 'Idle'}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Bottom Row: Train Table (full width) */}
                    <div className="lg:col-span-12" style={{ minHeight: '400px' }}>
                        <TrainTable
                            trains={trains}
                            onTrainSelect={handleTrainSelect}
                            onTrainClick={handleTrainClick}
                            loading={isLoading}
                            highlightDelayed
                        />
                    </div>
                </div>
            </div>
        </MainLayout>
    );
};

export default Dashboard;
