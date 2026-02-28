import { Map, AlertTriangle, Train, Building2 } from 'lucide-react';
import { useLiveData } from '../context/LiveDataContext';
import { cn } from '../utils/cn';

export function NetworkMap() {
  const { sections, trains, platforms } = useLiveData();

  const getTrainColor = (type: string) => {
    if (type === 'express') return 'bg-blue-600';
    if (type === 'passenger') return 'bg-emerald-600';
    return 'bg-amber-600';
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">Network Graph</h2>
          <p className="text-sm text-zinc-500 mt-1">Live section occupancy and congestion probabilities</p>
        </div>
        <div className="flex gap-4">
          <div className="flex items-center gap-2 text-sm text-zinc-600">
            <div className="w-3 h-3 rounded-full bg-emerald-500" /> Clear
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-600">
            <div className="w-3 h-3 rounded-full bg-amber-500" /> Congested
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-600">
            <div className="w-3 h-3 rounded-full bg-red-500" /> Blocked
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-zinc-950 rounded-2xl border border-zinc-800 p-8 min-h-[500px] relative overflow-hidden flex flex-col">
          <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(#3f3f46 1px, transparent 1px)', backgroundSize: '24px 24px' }} />
          
          <div className="relative z-10 flex-1 grid grid-cols-3 gap-8 p-8">
            {sections.map((section, i) => {
              const trainsInSection = trains.filter(t => t.currentSection === section.id);
              
              return (
                <div key={section.id} className={cn(
                  "relative p-4 rounded-xl border-2 transition-all duration-300 flex flex-col justify-between",
                  section.status === 'clear' ? "bg-zinc-900/80 border-emerald-500/30 hover:border-emerald-500/50" :
                  section.status === 'congested' ? "bg-amber-950/30 border-amber-500/50 hover:border-amber-500/80" :
                  "bg-red-950/30 border-red-500/50 hover:border-red-500/80",
                  i % 2 === 0 ? "mt-12" : "mb-12"
                )}>
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <span className="text-xs font-mono text-zinc-400">{section.id}</span>
                      <h4 className="text-sm font-semibold text-zinc-200 mt-1">{section.name}</h4>
                    </div>
                    {section.congestionProbability > 0.7 && (
                      <AlertTriangle className="w-4 h-4 text-amber-500 animate-pulse" />
                    )}
                  </div>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Occupancy</span>
                      <span className="text-zinc-300 font-mono">{section.currentOccupancy} / {section.capacity}</span>
                    </div>
                    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div 
                        className={cn(
                          "h-full rounded-full transition-all duration-500",
                          section.currentOccupancy / section.capacity > 0.8 ? "bg-red-500" :
                          section.currentOccupancy / section.capacity > 0.5 ? "bg-amber-500" : "bg-emerald-500"
                        )}
                        style={{ width: `${(section.currentOccupancy / section.capacity) * 100}%` }}
                      />
                    </div>
                    
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Congestion Prob.</span>
                      <span className={cn(
                        "font-mono",
                        section.congestionProbability > 0.7 ? "text-amber-500" : "text-emerald-500"
                      )}>
                        {(section.congestionProbability * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  {trainsInSection.length > 0 && (
                    <div className="absolute -top-3 -right-3 flex gap-1">
                      {trainsInSection.map(t => (
                        <div key={t.id} className={cn(
                          "w-6 h-6 rounded-full border-2 border-zinc-950 flex items-center justify-center shadow-lg transition-colors",
                          getTrainColor(t.type)
                        )} title={`${t.name} (${t.type})`}>
                          <Train className="w-3 h-3 text-white" />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm">
            <h3 className="text-base font-semibold text-zinc-900 mb-4">Hot Sections</h3>
            <div className="space-y-4">
              {[...sections].sort((a, b) => b.congestionProbability - a.congestionProbability).slice(0, 4).map(section => (
                <div key={section.id} className="flex items-center justify-between p-3 rounded-lg border border-amber-100 bg-amber-50/50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-900">{section.name}</span>
                      <span className="text-[10px] font-mono text-zinc-500 bg-zinc-100 px-1.5 py-0.5 rounded">{section.id}</span>
                    </div>
                    <p className="text-xs text-zinc-500 mt-1">Occupancy: {section.currentOccupancy}/{section.capacity}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-lg font-light text-amber-600">{(section.congestionProbability * 100).toFixed(0)}%</span>
                    <p className="text-[10px] text-amber-600/70 uppercase tracking-wider font-semibold">Prob</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-zinc-900">Platform Status</h3>
              <Building2 className="w-4 h-4 text-zinc-400" />
            </div>
            <div className="space-y-3">
              {platforms.map(platform => (
                <div key={platform.id} className="flex items-center justify-between p-3 rounded-lg border border-zinc-100 bg-zinc-50/50">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-900">{platform.stationName}</span>
                      <span className="text-[10px] font-mono text-zinc-500 bg-zinc-200 px-1.5 py-0.5 rounded">P{platform.platformNumber}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    {platform.isOccupied ? (
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100">
                        <Train className="w-3 h-3" />
                        {platform.occupyingTrainId}
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                        Available
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
