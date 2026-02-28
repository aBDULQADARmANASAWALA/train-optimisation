import { Terminal, Database, ShieldAlert, CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import { cn } from '../utils/cn';

const MOCK_LOGS = [
  { id: 1, time: '10:35:12', level: 'info', component: 'STATE_ENGINE', message: 'Read live Supabase data: 6 active trains, 6 sections.' },
  { id: 2, time: '10:35:14', level: 'info', component: 'STATE_ENGINE', message: 'Built NetworkX graph. Detected 2 current conflicts.' },
  { id: 3, time: '10:35:18', level: 'warn', component: 'ML_PREDICTOR', message: 'Predicted high congestion probability (0.85) for S-14.' },
  { id: 4, time: '10:35:25', level: 'info', component: 'CP_SAT_OPTIMIZER', message: 'Solving for next 60 minutes. Minimizing delay...' },
  { id: 5, time: '10:35:42', level: 'success', component: 'CP_SAT_OPTIMIZER', message: 'Solution found. Total delay reduced by 45m. Constraints respected.' },
  { id: 6, time: '10:35:45', level: 'info', component: 'VALIDATE_PERSIST', message: 'Writing optimized_schedule back to Supabase.' },
  { id: 7, time: '10:35:48', level: 'success', component: 'VALIDATE_PERSIST', message: 'Updated train_state with new expected delays.' },
];

export function LogsView() {
  return (
    <div className="p-8 max-w-7xl mx-auto h-[calc(100vh-4rem)] flex flex-col">
      <div className="flex items-center justify-between mb-8 flex-shrink-0">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">System Logs</h2>
          <p className="text-sm text-zinc-500 mt-1">Real-time orchestration cycle events</p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-white border border-zinc-200 rounded-lg text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors shadow-sm flex items-center gap-2">
            <Database className="w-4 h-4" />
            View Supabase
          </button>
          <button className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors shadow-sm flex items-center gap-2">
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
          {MOCK_LOGS.map((log) => (
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
