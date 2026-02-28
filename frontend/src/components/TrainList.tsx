import { Train, AlertCircle, CheckCircle2, Clock } from 'lucide-react';
import { useLiveData } from '../context/LiveDataContext';
import { cn } from '../utils/cn';

export function TrainList() {
  const { trains } = useLiveData();

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">Active Trains</h2>
          <p className="text-sm text-zinc-500 mt-1">Live tracking and predicted delays</p>
        </div>
        <div className="flex gap-2">
          <input 
            type="text" 
            placeholder="Search trains..." 
            className="px-4 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-64"
          />
          <select className="px-4 py-2 border border-zinc-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
            <option>All Types</option>
            <option>Express</option>
            <option>Passenger</option>
            <option>Freight</option>
          </select>
        </div>
      </div>

      <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-zinc-50 border-b border-zinc-200">
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Train ID</th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Name & Type</th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Current Section</th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Priority</th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Predicted Delay</th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {trains.map((train) => (
                <tr key={train.id} className="hover:bg-zinc-50/50 transition-colors group">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center border border-zinc-200">
                        <Train className="w-4 h-4 text-zinc-600" />
                      </div>
                      <span className="font-mono text-sm font-medium text-zinc-900">{train.id}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-zinc-900">{train.name}</span>
                      <span className="text-xs text-zinc-500 capitalize">{train.type}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-zinc-100 text-zinc-800 border border-zinc-200 font-mono">
                      {train.currentSection}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <div className="flex space-x-0.5">
                        {[...Array(5)].map((_, i) => (
                          <div 
                            key={i} 
                            className={cn(
                              "w-1.5 h-3 rounded-full",
                              i < (train.priorityWeight / 2) ? "bg-blue-500" : "bg-zinc-200"
                            )}
                          />
                        ))}
                      </div>
                      <span className="text-xs font-medium text-zinc-500 ml-2">{train.priorityWeight}/10</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <Clock className={cn(
                        "w-4 h-4",
                        train.predictedDelayMinutes > 10 ? "text-red-500" : 
                        train.predictedDelayMinutes > 0 ? "text-amber-500" : "text-emerald-500"
                      )} />
                      <span className={cn(
                        "text-sm font-medium",
                        train.predictedDelayMinutes > 10 ? "text-red-600" : 
                        train.predictedDelayMinutes > 0 ? "text-amber-600" : "text-emerald-600"
                      )}>
                        {train.predictedDelayMinutes > 0 ? `+${train.predictedDelayMinutes} min` : 'On Time'}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={cn(
                      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
                      train.status === 'on_time' ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                      train.status === 'delayed' ? "bg-amber-50 text-amber-700 border-amber-200" :
                      "bg-red-50 text-red-700 border-red-200"
                    )}>
                      {train.status === 'on_time' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                      {train.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button className="text-blue-600 hover:text-blue-900 opacity-0 group-hover:opacity-100 transition-opacity">
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
