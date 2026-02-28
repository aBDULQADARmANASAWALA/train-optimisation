import React, { useMemo } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from 'recharts';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface KPISnapshot {
    timestamp: number;
    totalWeightedDelay: number;
    averageDelay: number;
    throughput: number;
    sectionUtilization: number;
    onTimePercentage: number;
    capacityUtilization: number;
    systemEfficiency: number;
}

export interface KPIHistoryEntry extends KPISnapshot {
    id: string;
}

export interface KPIPanelProps {
    current: KPISnapshot | null;
    history: KPIHistoryEntry[];
    loading?: boolean;
    error?: string | null;
    onRefresh?: () => void;
    colorScheme?: KPIColorScheme;
}

export interface KPIColorScheme {
    primary: string;
    secondary: string;
    success: string;
    warning: string;
    danger: string;
    neutral: string;
    chartLine1: string;
    chartLine2: string;
    chartLine3: string;
    chartBackground: string;
    cardBackground: string;
}

// ============================================================================
// Color Scheme
// ============================================================================

const DEFAULT_COLOR_SCHEME: KPIColorScheme = {
    primary: '#06b6d4', // cyan-500
    secondary: '#8b5cf6', // violet-500
    success: '#22c55e', // green-500
    warning: '#f97316', // orange-500
    danger: '#ef4444', // red-500
    neutral: '#64748b', // slate-500
    chartLine1: '#06b6d4', // cyan
    chartLine2: '#22c55e', // green
    chartLine3: '#f97316', // orange
    chartBackground: '#1e293b', // slate-900
    cardBackground: '#0f172a', // slate-950
};

// ============================================================================
// KPI Card Component
// ============================================================================

interface KPICardProps {
    title: string;
    value: number;
    unit: string;
    trend?: 'up' | 'down' | 'stable';
    trendPercent?: number;
    thresholdWarning?: number;
    thresholdCritical?: number;
    bgColor: string;
    textColor: string;
    secondaryText?: string;
}

const KPICard: React.FC<KPICardProps> = React.memo(
    ({
        title,
        value,
        unit,
        trend,
        trendPercent,
        thresholdWarning,
        thresholdCritical,
        bgColor,
        textColor,
        secondaryText,
    }) => {
        let statusIndicator = 'bg-slate-600'; // neutral

        if (thresholdCritical && value >= thresholdCritical) {
            statusIndicator = 'bg-red-500';
        } else if (thresholdWarning && value >= thresholdWarning) {
            statusIndicator = 'bg-orange-500';
        } else {
            statusIndicator = 'bg-green-500';
        }

        const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→';
        const trendColor = trend === 'up' ? 'text-red-400' : trend === 'down' ? 'text-green-400' : 'text-slate-400';

        return (
            <div
                className="p-4 rounded-lg border border-slate-700 shadow-md hover:shadow-lg transition-shadow"
                style={{ backgroundColor: bgColor }}
            >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                    <div>
                        <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
                        <div className="flex items-baseline gap-2 mt-2">
                            <span className={`text-2xl font-bold ${textColor}`}>{value.toFixed(1)}</span>
                            <span className="text-sm text-slate-400">{unit}</span>
                        </div>
                    </div>
                    <div className={`w-3 h-3 rounded-full ${statusIndicator}`} />
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between text-xs text-slate-400">
                    {secondaryText && <span>{secondaryText}</span>}
                    {trend && trendPercent !== undefined && (
                        <span className={`flex items-center gap-1 ${trendColor}`}>
                            <span>{trendIcon}</span>
                            <span>{Math.abs(trendPercent).toFixed(1)}%</span>
                        </span>
                    )}
                </div>
            </div>
        );
    }
);

KPICard.displayName = 'KPICard';

// ============================================================================
// KPI Chart Component
// ============================================================================

interface KPIChartProps {
    data: KPIHistoryEntry[];
    colorScheme: KPIColorScheme;
    height?: number;
}

const KPIChart: React.FC<KPIChartProps> = React.memo(({ data, colorScheme, height = 300 }) => {
    // Format data for Recharts
    const chartData = useMemo(() => {
        return data.map((entry) => ({
            timestamp: new Date(entry.timestamp).toLocaleTimeString(),
            'Avg Delay': Math.round(entry.averageDelay * 10) / 10,
            'Utilization': Math.round(entry.sectionUtilization),
            'Efficiency': Math.round(entry.systemEfficiency * 100),
        }));
    }, [data]);

    return (
        <div className="w-full rounded-lg border border-slate-700 p-4 shadow-md" style={{ backgroundColor: colorScheme.cardBackground }}>
            <h3 className="text-sm font-semibold text-slate-300 mb-4">KPI Trends</h3>
            <ResponsiveContainer width="100%" height={height}>
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colorScheme.neutral} opacity={0.2} />
                    <XAxis
                        dataKey="timestamp"
                        tick={{ fill: colorScheme.neutral, fontSize: 12 }}
                        stroke={colorScheme.neutral}
                        opacity={0.5}
                    />
                    <YAxis
                        tick={{ fill: colorScheme.neutral, fontSize: 12 }}
                        stroke={colorScheme.neutral}
                        opacity={0.5}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: colorScheme.cardBackground,
                            border: `1px solid ${colorScheme.neutral}`,
                            borderRadius: '8px',
                        }}
                        labelStyle={{ color: colorScheme.primary }}
                        cursor={{ stroke: colorScheme.primary, opacity: 0.3 }}
                    />
                    <Legend />
                    <Line
                        type="monotone"
                        dataKey="Avg Delay"
                        stroke={colorScheme.chartLine1}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="Utilization"
                        stroke={colorScheme.chartLine2}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="Efficiency"
                        stroke={colorScheme.chartLine3}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
});

KPIChart.displayName = 'KPIChart';

// ============================================================================
// KPI Panel Component
// ============================================================================

const KPIPanel: React.FC<KPIPanelProps> = React.memo(
    ({
        current,
        history,
        loading = false,
        error = null,
        onRefresh,
        colorScheme = DEFAULT_COLOR_SCHEME,
    }) => {
        if (loading) {
            return (
                <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                        <div className="animate-spin inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mb-3" />
                        <p className="text-slate-400">Loading KPI data...</p>
                    </div>
                </div>
            );
        }

        if (error) {
            return (
                <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                        <p className="text-red-400 font-semibold mb-2">Error Loading KPIs</p>
                        <p className="text-slate-400 text-sm mb-4">{error}</p>
                        <button
                            onClick={onRefresh}
                            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded font-medium transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            );
        }

        return (
            <div className="w-full h-full flex flex-col gap-6 p-6" style={{ backgroundColor: colorScheme.cardBackground }}>
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold text-cyan-400">Key Performance Indicators</h2>
                    {onRefresh && (
                        <button
                            onClick={onRefresh}
                            className="px-3 py-1 text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition-colors"
                            aria-label="Refresh KPI data"
                        >
                            ↻ Refresh
                        </button>
                    )}
                </div>

                {/* KPI Cards Grid */}
                {current && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <KPICard
                            title="Average Delay"
                            value={current.averageDelay}
                            unit="minutes"
                            bgColor={colorScheme.cardBackground}
                            textColor="text-cyan-400"
                            secondaryText="System delay"
                        />
                        <KPICard
                            title="On-Time %"
                            value={current.onTimePercentage}
                            unit="%"
                            thresholdWarning={80}
                            thresholdCritical={70}
                            bgColor={colorScheme.cardBackground}
                            textColor="text-green-400"
                            secondaryText="Trains on schedule"
                        />
                        <KPICard
                            title="Section Utilization"
                            value={current.sectionUtilization}
                            unit="%"
                            thresholdWarning={70}
                            thresholdCritical={85}
                            bgColor={colorScheme.cardBackground}
                            textColor="text-orange-400"
                            secondaryText="Track occupancy"
                        />
                        <KPICard
                            title="System Efficiency"
                            value={current.systemEfficiency}
                            unit="score"
                            thresholdWarning={0.7}
                            thresholdCritical={0.5}
                            bgColor={colorScheme.cardBackground}
                            textColor="text-violet-400"
                            secondaryText="Overall performance"
                        />
                    </div>
                )}

                {/* Chart */}
                {history.length > 0 && (
                    <KPIChart data={history} colorScheme={colorScheme} height={300} />
                )}

                {/* Empty State */}
                {!current && history.length === 0 && (
                    <div className="flex items-center justify-center flex-1">
                        <div className="text-center">
                            <p className="text-slate-400 mb-2">No KPI data available</p>
                            <p className="text-slate-500 text-sm mb-4">Data will appear once the system starts tracking metrics</p>
                            {onRefresh && (
                                <button
                                    onClick={onRefresh}
                                    className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded font-medium transition-colors"
                                >
                                    Load Data
                                </button>
                            )}
                        </div>
                    </div>
                )}
            </div>
        );
    }
);

KPIPanel.displayName = 'KPIPanel';

export default KPIPanel;
