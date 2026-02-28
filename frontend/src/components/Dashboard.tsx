import { Activity, AlertOctagon, TrendingDown, Clock, Train, Map, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useLiveData } from '../context/LiveDataContext';
import { cn } from '../utils/cn';
import { useState } from 'react';
import { api } from '../api';
import { LoadingOverlay } from './LoadingOverlay';
import { OptimizationPlanPanel } from './OptimizationPlanPanel';

const trendData = [
  { time: '10:00', delay: 120 },
  { time: '10:05', delay: 110 },
  { time: '10:10', delay: 90 },
  { time: '10:15', delay: 130 },
  { time: '10:20', delay: 85 },
  { time: '10:25', delay: 60 },
  { time: '10:30', delay: 45 },
];

export function Dashboard() {
  const { trains, sections, conflicts, runs, metrics, loading, error, refreshData } = useLiveData();
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [planRefreshTrigger, setPlanRefreshTrigger] = useState(0);

  const handleOptimization = async () => {
    try {
      setIsOptimizing(true);
      await api.runOptimization();
      await refreshData();
      setPlanRefreshTrigger(t => t + 1); // reload the plan panel
    } catch (err) {
      console.error("Failed to run optimization:", err);
      alert("Failed to run optimization. Check console for details.");
    } finally {
      setIsOptimizing(false);
    }
  };

  const activeConflicts = conflicts.filter(c => !c.resolved);
  // Use backend metrics total when available (more accurate - reflects actual DB state)
  // Fall back to summing client-side train delays
  const totalDelay = metrics
    ? Math.round(metrics.total_weighted_delay_minutes)
    : Math.round(trains.reduce((acc, t) => acc + t.predictedDelayMinutes, 0));
  const congestedSections = sections.filter(s => s.status === 'congested' || s.status === 'blocked').length;

  // Cumulative delay saved by all optimization runs
  const totalDelayReduced = runs.reduce((acc, r) => acc + r.totalDelayReduced, 0);

  const delayData = trains.map(t => ({
    name: t.name || t.id,
    delay: Math.round(t.predictedDelayMinutes),
    type: t.type
  })).sort((a, b) => b.delay - a.delay).slice(0, 10);

  return (
    <>
      {isOptimizing && <LoadingOverlay message="Running Optimization Engine..." />}
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">System Overview</h2>
          <div className="flex gap-2">
            <button className="px-4 py-2 bg-white border border-zinc-200 rounded-lg text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors shadow-sm">
              Export Report
            </button>
            <button
              onClick={handleOptimization}
              disabled={isOptimizing}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
            >
              {isOptimizing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                  Optimizing...
                </>
              ) : "Force Optimization"}
            </button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-500">Active Conflicts</h3>
              <div className="w-8 h-8 rounded-full bg-red-50 flex items-center justify-center">
                <AlertOctagon className="w-4 h-4 text-red-500" />
              </div>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-light text-zinc-900">{activeConflicts.length}</span>
              <span className="text-sm text-red-500 font-medium mb-1">Requires attention</span>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-500">Total Predicted Delay</h3>
              <div className="w-8 h-8 rounded-full bg-amber-50 flex items-center justify-center">
                <Clock className="w-4 h-4 text-amber-500" />
              </div>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-light text-zinc-900">{totalDelay}</span>
              <span className="text-sm text-zinc-500 font-medium mb-1">minutes</span>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-500">Congested Sections</h3>
              <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center">
                <Map className="w-4 h-4 text-blue-500" />
              </div>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-light text-zinc-900">{congestedSections}</span>
              <span className="text-sm text-zinc-500 font-medium mb-1">/ {sections.length} total</span>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-500">Delay Avoided (Cumulative)</h3>
              <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center">
                <TrendingDown className="w-4 h-4 text-emerald-500" />
              </div>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-light text-zinc-900">{Math.round(totalDelayReduced)}</span>
              <span className="text-sm text-emerald-500 font-medium mb-1">minutes saved</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Predicted Delays Chart */}
          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-base font-semibold text-zinc-900">Predicted Delays</h3>
                <p className="text-xs text-zinc-500">ML Predictor (next 60 min)</p>
              </div>
              <Clock className="w-4 h-4 text-zinc-400" />
            </div>
            <div className="w-full" style={{ height: 250, minHeight: 250, minWidth: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={delayData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e4e7" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#71717a', fontSize: 12 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#71717a', fontSize: 12 }} />
                  <Tooltip
                    cursor={{ fill: '#f4f4f5' }}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e4e4e7', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Bar dataKey="delay" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Current Conflicts Table */}
          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-base font-semibold text-zinc-900">Current Conflicts</h3>
                <p className="text-xs text-zinc-500">Identified by State Engine</p>
              </div>
              <AlertOctagon className="w-4 h-4 text-zinc-400" />
            </div>
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-zinc-100">
                    <th className="pb-3 text-xs font-semibold text-zinc-500 uppercase">Location</th>
                    <th className="pb-3 text-xs font-semibold text-zinc-500 uppercase">Type</th>
                    <th className="pb-3 text-xs font-semibold text-zinc-500 uppercase">Trains</th>
                    <th className="pb-3 text-xs font-semibold text-zinc-500 uppercase">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-50">
                  {activeConflicts.map((conflict) => (
                    <tr key={conflict.id} className="hover:bg-zinc-50/50">
                      <td className="py-3 text-sm font-mono text-zinc-900">{conflict.location}</td>
                      <td className="py-3 text-sm text-zinc-600 capitalize">{conflict.type}</td>
                      <td className="py-3 text-sm text-zinc-600">
                        <div className="flex gap-1">
                          {conflict.trainsInvolved.map(t => (
                            <span key={t} className="px-1.5 py-0.5 bg-zinc-100 rounded text-xs font-mono">{t}</span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3">
                        <span className={cn(
                          "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                          conflict.severity === 'high' ? "bg-red-50 text-red-700" :
                            conflict.severity === 'medium' ? "bg-amber-50 text-amber-700" :
                              "bg-blue-50 text-blue-700"
                        )}>
                          {conflict.severity}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {activeConflicts.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-sm text-zinc-500">
                        No active conflicts detected.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Congestion Probability List */}
          <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-base font-semibold text-zinc-900">Congestion Probability</h3>
                <p className="text-xs text-zinc-500">ML Predictor Hot Sections</p>
              </div>
              <Map className="w-4 h-4 text-zinc-400" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sections.sort((a, b) => b.congestionProbability - a.congestionProbability).slice(0, 6).map(section => (
                <div key={section.id} className="flex items-center justify-between p-4 rounded-xl border border-zinc-100 bg-zinc-50/50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-900">{section.name}</span>
                      <span className="text-[10px] font-mono text-zinc-500 bg-white px-1.5 py-0.5 rounded border border-zinc-200">{section.id}</span>
                    </div>
                    <div className="w-full h-1.5 bg-zinc-200 rounded-full mt-3 overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-500",
                          section.congestionProbability > 0.8 ? "bg-red-500" :
                            section.congestionProbability > 0.5 ? "bg-amber-500" : "bg-emerald-500"
                        )}
                        style={{ width: `${section.congestionProbability * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    <span className={cn(
                      "text-lg font-light",
                      section.congestionProbability > 0.8 ? "text-red-600" :
                        section.congestionProbability > 0.5 ? "text-amber-600" : "text-emerald-600"
                    )}>
                      {(section.congestionProbability * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Optimization Plan Panel — replaces static history list */}
          <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-zinc-100 pb-4 mb-0">
              <h3 className="text-base font-semibold text-zinc-900">Recent Runs</h3>
              <Activity className="w-4 h-4 text-zinc-400" />
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto p-6 pt-4 pr-2">
              {runs.slice(0, 5).map((run) => (
                <div key={run.id} className="flex items-start gap-4 p-4 rounded-xl border border-zinc-100 bg-zinc-50/50">
                  <div className={cn(
                    "w-2 h-2 rounded-full mt-1.5",
                    run.status === 'success' ? "bg-emerald-500" : "bg-red-500"
                  )} />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-zinc-900">{run.id}</span>
                      <span className="text-xs text-zinc-500 font-mono">
                        {new Date(run.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="text-xs text-zinc-600 flex items-center gap-3">
                      <span>-{run.totalDelayReduced}m delay</span>
                      <span className="w-1 h-1 rounded-full bg-zinc-300" />
                      <span>{run.conflictsResolved} conflicts fixed</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Optimization Plan — full width below the grid */}
        <OptimizationPlanPanel refreshTrigger={planRefreshTrigger} />
      </div>
    </>
  );
}
