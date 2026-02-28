import { Clock, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '../utils/cn';
import { useLiveData } from '../context/LiveDataContext';

export function Header({ systemStatus }: { systemStatus: 'running' | 'frozen'; }) {
  const { metrics, conflicts, loading } = useLiveData();
  const lastRunTimestamp = metrics?.timestamp || new Date().toISOString();
  const activeConflicts = conflicts.filter(c => !c.resolved).length;
  return (
    <header className="h-16 bg-white border-b border-zinc-200 flex items-center justify-between px-6 shadow-sm z-10">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-2.5 h-2.5 rounded-full animate-pulse",
            systemStatus === 'running' ? "bg-emerald-500" : "bg-red-500"
          )} />
          <span className="text-sm font-semibold text-zinc-900 tracking-tight">
            {systemStatus === 'running' ? 'SYSTEM ONLINE' : 'SYSTEM FROZEN'}
          </span>
        </div>

        <div className="h-4 w-px bg-zinc-300" />

        <div className="flex items-center gap-2 text-sm text-zinc-600">
          <Clock className="w-4 h-4" />
          <span className="font-mono text-xs">Horizon: 60m</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-100 rounded-md text-xs font-medium text-zinc-600 border border-zinc-200">
          <RefreshCw className="w-3.5 h-3.5" />
          Last Opt: {new Date(lastRunTimestamp).toLocaleTimeString()}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-100">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Persisted
          </div>
          <div className="flex items-center gap-1.5 text-xs font-medium text-amber-600 bg-amber-50 px-2 py-1 rounded-md border border-amber-100">
            <AlertTriangle className="w-3.5 h-3.5" />
            {activeConflicts} {activeConflicts === 1 ? 'Conflict' : 'Conflicts'}
          </div>
        </div>
      </div>
    </header>
  );
}
