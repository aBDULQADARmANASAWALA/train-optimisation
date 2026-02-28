import { Activity, Train, Map, Calendar, Settings, ShieldAlert } from 'lucide-react';
import { cn } from '../utils/cn';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  systemStatus: 'running' | 'frozen';
  setSystemStatus: (status: 'running' | 'frozen') => void;
}

export function Sidebar({ activeTab, setActiveTab, systemStatus, setSystemStatus }: SidebarProps) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'trains', label: 'Active Trains', icon: Train },
    { id: 'network', label: 'Network Map', icon: Map },
    { id: 'schedule', label: 'Schedule', icon: Calendar },
    { id: 'logs', label: 'System Logs', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-zinc-950 text-zinc-300 flex flex-col h-full border-r border-zinc-800">
      <div className="p-6 flex items-center gap-3 border-b border-zinc-800">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold">
          R
        </div>
        <div>
          <h1 className="text-sm font-bold text-white tracking-wider uppercase">RailOrchestra</h1>
          <p className="text-[10px] text-zinc-500 font-mono">v2.4.1-beta</p>
        </div>
      </div>

      <nav className="flex-1 py-6 px-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                isActive 
                  ? "bg-blue-600/10 text-blue-400" 
                  : "hover:bg-zinc-900 hover:text-white"
              )}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-zinc-800">
        <div className="bg-zinc-900 rounded-lg p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
            <ShieldAlert className="w-3.5 h-3.5" />
            Safety Net
          </div>
          <p className="text-[11px] text-zinc-500 mb-3 leading-relaxed">
            Dispatcher can freeze the system and fallback to last known good schedule.
          </p>
          <button 
            onClick={() => setSystemStatus(systemStatus === 'running' ? 'frozen' : 'running')}
            className={cn(
              "w-full py-2 px-3 rounded text-xs font-semibold transition-colors border",
              systemStatus === 'running' 
                ? "bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20"
                : "bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20"
            )}
          >
            {systemStatus === 'running' ? 'MANUAL OVERRIDE' : 'RESUME SYSTEM'}
          </button>
        </div>
      </div>
    </aside>
  );
}
