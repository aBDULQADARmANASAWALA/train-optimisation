import { Terminal, Database, ShieldAlert, CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import { cn } from '../utils/cn';
import { useLiveData } from '../context/LiveDataContext';
import { useMemo } from 'react';

interface LogEntry {
  id: number;
  time: string;
  level: 'info' | 'warn' | 'success' | 'error';
  component: string;
  message: string;
}

export function LogsView() {
  const { trains, sections, conflicts, runs } = useLiveData();

  const logs: LogEntry[] = useMemo(() => {
    const entries: LogEntry[] = [];
    let id = 1;
    const now = new Date();
    const fmt = (d: Date) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    // State engine summary
    const activeSections = sections.filter(s => s.currentOccupancy > 0).length;
    entries.push({ id: id++, time: fmt(now), level: 'info', component: 'STATE_ENGINE', message: `Read live Supabase data: ${trains.length} active trains, ${sections.length} sections (${activeSections} occupied).` });

    const activeConflicts = conflicts.filter(c => !c.resolved);
    if (activeConflicts.length > 0) {
      entries.push({ id: id++, time: fmt(now), level: 'warn', component: 'STATE_ENGINE', message: `Detected ${activeConflicts.length} active conflict${activeConflicts.length !== 1 ? 's' : ''}: ${activeConflicts.map(c => `${c.type} at ${c.location.substring(0, 8)}`).join(', ')}.` });
    } else {
      entries.push({ id: id++, time: fmt(now), level: 'success', component: 'STATE_ENGINE', message: 'No active conflicts detected.' });
    }

    // ML predictor summary
    const congestedSections = sections.filter(s => s.congestionProbability > 0.7);
    if (congestedSections.length > 0) {
      for (const s of congestedSections.slice(0, 3)) {
        entries.push({ id: id++, time: fmt(now), level: 'warn', component: 'ML_PREDICTOR', message: `High congestion probability (${(s.congestionProbability * 100).toFixed(0)}%) for ${s.name}.` });
      }
    } else {
      entries.push({ id: id++, time: fmt(now), level: 'info', component: 'ML_PREDICTOR', message: 'All sections below congestion threshold.' });
    }

    // Delayed trains
    const delayedTrains = trains.filter(t => t.predictedDelayMinutes > 0);
    if (delayedTrains.length > 0) {
      const totalDelay = delayedTrains.reduce((acc, t) => acc + t.predictedDelayMinutes, 0);
      entries.push({ id: id++, time: fmt(now), level: 'warn', component: 'STATE_ENGINE', message: `${delayedTrains.length} train${delayedTrains.length !== 1 ? 's' : ''} delayed, total accumulated delay: ${Math.round(totalDelay)} min.` });
    }

    // Optimization run history
    for (const run of runs.slice(0, 5)) {
      const runTime = new Date(run.timestamp);
      entries.push({ id: id++, time: fmt(runTime), level: run.status === 'success' ? 'success' : 'error', component: 'CP_SAT_OPTIMIZER', message: `Optimization run ${run.id.substring(0, 8)}: ${run.status}. Delay: ${run.totalDelayReduced.toFixed(1)} min, ${run.conflictsResolved} conflict${run.conflictsResolved !== 1 ? 's' : ''} addressed.` });
    }

    return entries;
  }, [trains, sections, conflicts, runs]);
  return (
    <div className="p-8 max-w-7xl mx-auto h-[calc(100vh-4rem)] flex flex-col">
      <div className="flex items-center justify-between mb-8 flex-shrink-0">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">System Logs</h2>
          <p className="text-sm text-zinc-500 mt-1">Real-time orchestration cycle events</p>
        </div>
        <div className="flex gap-2">
          <button
            disabled
            title="Opens Supabase dashboard (not connected)"
            className="px-4 py-2 bg-white border border-zinc-200 rounded-lg text-sm font-medium text-zinc-400 cursor-not-allowed shadow-sm flex items-center gap-2"
          >
            <Database className="w-4 h-4" />
            View Supabase
          </button>
          <button
            disabled
            title="Log view is generated from live state"
            className="px-4 py-2 bg-zinc-700 text-zinc-400 rounded-lg text-sm font-medium cursor-not-allowed shadow-sm flex items-center gap-2"
          >
            <Terminal className="w-4 h-4" />
            Clear Logs
          </button>
        </div>
      </div>

      <div className="flex-1 bg-zinc-950 rounded-2xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col font-mono text-sm">
        <div className="bg-zinc-900 px-6 py-3 border-b border-zinc-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50" />
              <div className="w-3 h-3 rounded-full bg-amber-500/20 border border-amber-500/50" />
              <div className="w-3 h-3 rounded-full bg-emerald-500/20 border border-emerald-500/50" />
            </div>
            <span className="text-zinc-500 text-xs">orchestrator.log</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Live Tail
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-4 hover:bg-zinc-900/50 p-1 -mx-1 rounded transition-colors group">
              <span className="text-zinc-600 flex-shrink-0 w-20">{log.time}</span>
              
              <div className="flex-shrink-0 w-6 flex justify-center mt-0.5">
                {log.level === 'info' && <Info className="w-4 h-4 text-blue-400" />}
                {log.level === 'warn' && <AlertTriangle className="w-4 h-4 text-amber-400" />}
                {log.level === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                {log.level === 'error' && <ShieldAlert className="w-4 h-4 text-red-400" />}
              </div>

              <span className={cn(
                "flex-shrink-0 w-40 font-semibold tracking-wider text-xs mt-0.5",
                log.component === 'STATE_ENGINE' ? "text-blue-400" :
                log.component === 'ML_PREDICTOR' ? "text-amber-400" :
                log.component === 'CP_SAT_OPTIMIZER' ? "text-cyan-400" :
                "text-emerald-400"
              )}>
                [{log.component}]
              </span>

              <span className={cn(
                "flex-1",
                log.level === 'info' ? "text-zinc-300" :
                log.level === 'warn' ? "text-amber-200" :
                log.level === 'success' ? "text-emerald-200" :
                "text-red-200"
              )}>
                {log.message}
              </span>
            </div>
          ))}
          <div className="flex items-center gap-2 text-zinc-600 pt-4">
            <span className="animate-pulse">_</span> Waiting for next orchestration cycle...
          </div>
        </div>
      </div>
    </div>
  );
}
