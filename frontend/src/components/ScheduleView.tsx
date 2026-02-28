import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { useLiveData } from '../context/LiveDataContext';
import { cn } from '../utils/cn';

export function ScheduleView() {
  const { trains } = useLiveData();

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">Train Schedule Status</h2>
          <p className="text-sm text-zinc-500 mt-1">Current accumulated delays from live state</p>
        </div>
      </div>

      <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200 bg-zinc-50/50 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-zinc-600">
              <div className="w-3 h-3 rounded-full bg-emerald-500" /> On Time
            </div>
            <div className="flex items-center gap-2 text-sm text-zinc-600">
              <div className="w-3 h-3 rounded-full bg-amber-500" /> Minor Delay
            </div>
            <div className="flex items-center gap-2 text-sm text-zinc-600">
              <div className="w-3 h-3 rounded-full bg-red-500" /> Delayed
            </div>
          </div>
          <div className="text-sm font-medium text-zinc-500 bg-zinc-100 px-3 py-1.5 rounded-lg border border-zinc-200">
            {trains.length} trains tracked
          </div>
        </div>

        <div className="divide-y divide-zinc-100">
          {[...trains].sort((a, b) => b.predictedDelayMinutes - a.predictedDelayMinutes).map((train) => (
            <div key={train.id} className="p-6 flex items-center gap-8 hover:bg-zinc-50/50 transition-colors">
              <div className="w-48 flex-shrink-0">
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-mono text-sm font-semibold text-zinc-900">{train.id.substring(0, 8)}</span>
                  <span className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wider",
                    train.type === 'express' ? "bg-blue-100 text-blue-700" :
                    train.type === 'passenger' ? "bg-emerald-100 text-emerald-700" :
                    "bg-amber-100 text-amber-700"
                  )}>
                    {train.type}
                  </span>
                </div>
                <p className="text-sm text-zinc-500">{train.name}</p>
              </div>

              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-3 h-3 rounded-full flex-shrink-0",
                    train.predictedDelayMinutes <= 0 ? "bg-emerald-500" :
                    train.predictedDelayMinutes <= 5 ? "bg-amber-400" : "bg-red-500"
                  )} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "text-sm font-medium",
                        train.predictedDelayMinutes <= 0 ? "text-emerald-700" :
                        train.predictedDelayMinutes <= 5 ? "text-amber-700" : "text-red-700"
                      )}>
                        {train.predictedDelayMinutes <= 0 ? 'On Schedule' : `+${Math.round(train.predictedDelayMinutes)} min delay`}
                      </span>
                      {train.predictedDelayMinutes <= 0 ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-amber-500" />
                      )}
                    </div>
                    {train.predictedDelayMinutes > 0 && (
                      <div className="w-full h-1.5 bg-zinc-100 rounded-full mt-2 overflow-hidden max-w-xs">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            train.predictedDelayMinutes <= 5 ? "bg-amber-400" : "bg-red-500"
                          )}
                          style={{ width: `${Math.min(100, (train.predictedDelayMinutes / 60) * 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 flex-shrink-0">
                <div className="text-right">
                  <div className="text-xs text-zinc-500">Section</div>
                  <div className="text-sm font-mono text-zinc-700">{train.currentSection?.substring(0, 8) || 'Terminal'}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-zinc-500">Priority</div>
                  <div className="text-sm font-medium text-zinc-700">{train.priorityWeight}/10</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
