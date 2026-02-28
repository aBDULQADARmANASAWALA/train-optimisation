import { useEffect, useState } from 'react';
import { CheckCircle, Clock, AlertTriangle, ChevronDown, ChevronUp, Zap, PlayCircle, TrendingDown, AlertCircle } from 'lucide-react';
import { api } from '../api';
import { OptimizationPlan, OptimizationPlanEntry } from '../types';
import { cn } from '../utils/cn';

const ACTION_CONFIG = {
    on_time: { label: 'Proceed', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', icon: CheckCircle, dot: 'bg-emerald-500' },
    minor_delay: { label: 'Minor Hold', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', icon: Clock, dot: 'bg-amber-400' },
    hold: { label: 'Hold Train', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200', icon: AlertTriangle, dot: 'bg-red-500' },
};

function TrainPlanCard({ entry, index }: { entry: OptimizationPlanEntry; index: number }) {
    const [expanded, setExpanded] = useState(index === 0);
    const cfg = ACTION_CONFIG[entry.action] || ACTION_CONFIG.on_time;
    const Icon = cfg.icon;

    const formatTime = (iso: string | null) => {
        if (!iso) return '—';
        try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
        catch { return '—'; }
    };

    return (
        <div className={cn('rounded-xl border overflow-hidden transition-all duration-200', cfg.border)}>
            {/* Header row */}
            <button
                onClick={() => setExpanded(e => !e)}
                className={cn('w-full flex items-center justify-between p-4 text-left', cfg.bg)}
            >
                <div className="flex items-center gap-3">
                    <div className={cn('w-2.5 h-2.5 rounded-full flex-shrink-0', cfg.dot)} />
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-zinc-900">{entry.train_number}</span>
                            <span className={cn('text-xs font-semibold px-2 py-0.5 rounded-full', cfg.bg, cfg.color, 'border', cfg.border)}>
                                <Icon className="w-3 h-3 inline mr-1" />
                                {cfg.label}
                            </span>
                        </div>
                        <p className={cn('text-xs mt-0.5 font-medium', cfg.color)}>
                            {entry.max_delay_minutes <= 0
                                ? 'Running on schedule — no action needed'
                                : `Absorb ${entry.max_delay_minutes} min delay across ${entry.stops.length} stop${entry.stops.length !== 1 ? 's' : ''}`}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {entry.max_delay_minutes > 0 && (
                        <span className="text-sm font-mono font-semibold text-zinc-700">
                            +{entry.max_delay_minutes}m
                        </span>
                    )}
                    {expanded ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
                </div>
            </button>

            {/* Expanded stop timeline */}
            {expanded && entry.stops.length > 0 && (
                <div className="bg-white px-4 pb-4 pt-2">
                    <div className="relative">
                        {/* Vertical timeline line */}
                        <div className="absolute left-[7px] top-2 bottom-2 w-px bg-zinc-200" />
                        <div className="space-y-3">
                            {entry.stops.map((stop, i) => (
                                <div key={i} className="flex items-start gap-3 pl-0.5">
                                    <div className={cn(
                                        'w-3.5 h-3.5 rounded-full border-2 flex-shrink-0 mt-0.5 z-10',
                                        stop.delay_minutes > 5 ? 'border-red-500 bg-red-100' :
                                            stop.delay_minutes > 0 ? 'border-amber-400 bg-amber-50' :
                                                'border-emerald-400 bg-emerald-50'
                                    )} />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between gap-2">
                                            <span className="text-sm font-medium text-zinc-800 truncate">
                                                {stop.station_name || `Stop ${stop.stop_order}`}
                                            </span>
                                            {stop.delay_minutes > 0 && (
                                                <span className="text-xs font-semibold text-red-600 flex-shrink-0">
                                                    +{stop.delay_minutes}m
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex gap-4 mt-0.5 text-xs text-zinc-500">
                                            <span>Scheduled: {formatTime(stop.scheduled_arrival)}</span>
                                            {stop.adjusted_arrival && stop.adjusted_arrival !== stop.scheduled_arrival && (
                                                <span className={cn(
                                                    'font-medium',
                                                    stop.delay_minutes > 0 ? 'text-red-500' : 'text-emerald-600'
                                                )}>
                                                    → Adjusted: {formatTime(stop.adjusted_arrival)}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

interface OptimizationPlanPanelProps {
    refreshTrigger: number; // bump this after each optimization run to force re-fetch
}

export function OptimizationPlanPanel({ refreshTrigger }: OptimizationPlanPanelProps) {
    const [plan, setPlan] = useState<OptimizationPlan | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        api.getOptimizationPlan()
            .then(data => { if (!cancelled) { setPlan(data); setLoading(false); } })
            .catch(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [refreshTrigger]);

    const holdCount = plan?.plan.filter(e => e.action === 'hold').length ?? 0;
    const delayCount = plan?.plan.filter(e => e.action === 'minor_delay').length ?? 0;
    const okCount = plan?.plan.filter(e => e.action === 'on_time').length ?? 0;

    return (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-zinc-100">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
                            <Zap className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-zinc-900">Optimization Plan</h3>
                            <p className="text-xs text-zinc-500">
                                {plan?.timestamp
                                    ? `Last run: ${new Date(plan.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
                                    : 'No plan generated yet'}
                            </p>
                        </div>
                    </div>
                    {plan?.available && (
                        <div className="flex items-center gap-3 text-xs">
                            {holdCount > 0 && (
                                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 text-red-700 rounded-full border border-red-100 font-medium">
                                    <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                                    {holdCount} hold
                                </span>
                            )}
                            {delayCount > 0 && (
                                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full border border-amber-100 font-medium">
                                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                                    {delayCount} slow
                                </span>
                            )}
                            {okCount > 0 && (
                                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-100 font-medium">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                    {okCount} clear
                                </span>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Summary bar */}
            {plan?.available && plan.plan.length > 0 && (
                <div className="px-6 py-3 bg-zinc-50 border-b border-zinc-100 flex items-center justify-between text-xs text-zinc-600">
                    <span>
                        OR-Tools CP-SAT • {plan.solver_runtime_seconds?.toFixed(1)}s solve time
                    </span>
                    <span className="font-semibold">
                        Total weighted delay: {plan.total_weighted_delay?.toFixed(1)} min
                    </span>
                </div>
            )}

            {/* Explanation Section */}
            {plan?.available && plan.explanation && (
                <div className="px-6 py-4 bg-gradient-to-br from-blue-50 to-indigo-50 border-b border-blue-100">
                    {/* Objective Improvement */}
                    {plan.explanation.objective_improvement && (
                        <div className="mb-4 flex items-center gap-4">
                            <div className="flex items-center gap-2">
                                <TrendingDown className="w-5 h-5 text-emerald-600" />
                                <div>
                                    <div className="text-xs text-zinc-600 font-medium">Delay Reduction</div>
                                    <div className="text-lg font-bold text-emerald-700">
                                        {plan.explanation.objective_improvement.improvement_percent.toFixed(1)}%
                                    </div>
                                </div>
                            </div>
                            <div className="text-xs text-zinc-600">
                                <span className="font-semibold">{plan.explanation.objective_improvement.delay_reduction.toFixed(1)} min</span> saved
                                <span className="text-zinc-400 mx-1">•</span>
                                {plan.explanation.objective_improvement.previous_weighted_delay.toFixed(1)} → {plan.explanation.objective_improvement.optimized_weighted_delay.toFixed(1)} min
                            </div>
                        </div>
                    )}

                    {/* Conflicts Detected */}
                    {plan.explanation.conflicts_detected && plan.explanation.conflicts_detected.length > 0 && (
                        <div className="mb-3">
                            <div className="text-xs font-semibold text-zinc-700 mb-2 flex items-center gap-1.5">
                                <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                                Conflicts Resolved ({plan.explanation.conflicts_detected.length})
                            </div>
                            <div className="space-y-1.5">
                                {plan.explanation.conflicts_detected.map((conflict, i) => (
                                    <div key={i} className="text-xs bg-white rounded-lg px-3 py-2 border border-blue-100">
                                        <div className="font-medium text-zinc-800">
                                            Section: <span className="text-blue-700">{conflict.section_name}</span>
                                        </div>
                                        <div className="text-zinc-600 mt-0.5">
                                            {conflict.competing_trains} trains competing • {conflict.train_numbers.join(', ')}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Decisions Made */}
                    {plan.explanation.decisions_made && plan.explanation.decisions_made.length > 0 && (
                        <div>
                            <div className="text-xs font-semibold text-zinc-700 mb-2">
                                Decisions ({plan.explanation.decisions_made.length})
                            </div>
                            <div className="space-y-1.5">
                                {plan.explanation.decisions_made.slice(0, 3).map((decision, i) => (
                                    <div key={i} className="text-xs bg-white rounded-lg px-3 py-2 border border-blue-100">
                                        <div className="text-zinc-700 leading-relaxed">
                                            {decision.explanation}
                                        </div>
                                    </div>
                                ))}
                                {plan.explanation.decisions_made.length > 3 && (
                                    <div className="text-xs text-zinc-500 text-center pt-1">
                                        +{plan.explanation.decisions_made.length - 3} more decisions
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Content */}
            <div className="p-6">
                {loading ? (
                    <div className="flex items-center justify-center py-12">
                        <div className="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
                        <span className="ml-3 text-sm text-zinc-500">Loading plan...</span>
                    </div>
                ) : !plan?.available ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mb-3">
                            <PlayCircle className="w-6 h-6 text-zinc-400" />
                        </div>
                        <p className="text-sm font-medium text-zinc-700">No plan yet</p>
                        <p className="text-xs text-zinc-500 mt-1">
                            Click "Force Optimization" to generate actionable recommendations
                        </p>
                    </div>
                ) : plan.plan.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <CheckCircle className="w-10 h-10 text-emerald-400 mb-3" />
                        <p className="text-sm font-medium text-zinc-700">No adjustments needed</p>
                        <p className="text-xs text-zinc-500 mt-1">All trains are running within acceptable bounds</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {/* Sort: hold first, then minor_delay, then on_time */}
                        {[...plan.plan]
                            .sort((a, b) => {
                                const order = { hold: 0, minor_delay: 1, on_time: 2 };
                                return (order[a.action] ?? 3) - (order[b.action] ?? 3);
                            })
                            .map((entry, i) => (
                                <TrainPlanCard key={entry.train_id} entry={entry} index={i} />
                            ))}
                    </div>
                )}
            </div>
        </div>
    );
}
