import { Calendar, Clock, ArrowRight } from 'lucide-react';
import { useLiveData } from '../context/LiveDataContext';
import { cn } from '../utils/cn';

export function ScheduleView() {
  const { trains } = useLiveData();

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">Optimized Schedule</h2>
          <p className="text-sm text-zinc-500 mt-1">Next 60 minutes arrival/departure times</p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-white border border-zinc-200 rounded-lg text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors shadow-sm">
            Export CSV
          </button>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm">
            Apply Schedule
          </button>
        </div>
      </div>

      <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200 bg-zinc-50/50 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-zinc-600">
              <div className="w-3 h-3 rounded-full bg-blue-500" /> Original Time
            </div>
            <div className="flex items-center gap-2 text-sm text-zinc-600">
              <div className="w-3 h-3 rounded-full bg-emerald-500" /> Optimized Time
            </div>
          </div>
          <div className="text-sm font-medium text-zinc-500 bg-zinc-100 px-3 py-1.5 rounded-lg border border-zinc-200">
            Time Window: 10:00 - 11:00
          </div>
        </div>

        <div className="divide-y divide-zinc-100">
          {trains.map((train, i) => {
            const originalTime = new Date();
            originalTime.setMinutes(originalTime.getMinutes() + i * 10);
            
            const optimizedTime = new Date(originalTime);
            optimizedTime.setMinutes(optimizedTime.getMinutes() - train.predictedDelayMinutes);

            return (
              <div key={train.id} className="p-6 flex items-center gap-8 hover:bg-zinc-50/50 transition-colors">
                <div className="w-48 flex-shrink-0">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-mono text-sm font-semibold text-zinc-900">{train.id}</span>
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

                <div className="flex-1 flex items-center gap-6">
                  <div className="flex-1 relative h-12 flex items-center">
                    <div className="absolute inset-0 border-b border-dashed border-zinc-200 top-1/2 -translate-y-1/2" />
                    
                    <div className="relative z-10 flex items-center justify-between w-full px-4">
                      <div className="flex flex-col items-center gap-2">
                        <span className="text-xs font-mono text-zinc-500 line-through opacity-60">
                          {originalTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <div className="w-3 h-3 rounded-full bg-blue-500 border-2 border-white shadow-sm" />
                      </div>

                      <ArrowRight className="w-4 h-4 text-zinc-300" />

                      <div className="flex flex-col items-center gap-2">
                        <span className="text-sm font-mono font-bold text-emerald-600">
                          {optimizedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <div className="w-4 h-4 rounded-full bg-emerald-500 border-2 border-white shadow-sm ring-4 ring-emerald-500/20" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="w-32 flex-shrink-0 text-right">
                  <div className="text-sm font-medium text-zinc-900 mb-1">
                    {train.predictedDelayMinutes > 0 ? `Saved ${train.predictedDelayMinutes}m` : 'On Time'}
                  </div>
                  <div className="text-xs text-zinc-500">
                    Priority: {train.priorityWeight}/10
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
