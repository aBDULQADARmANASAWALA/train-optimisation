import { useState } from 'react';
import { Activity, Train, Map, Calendar, Settings, ShieldAlert, Zap, CheckCircle, AlertTriangle } from 'lucide-react';
import { cn } from '../utils/cn';
import { api } from '../api';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  systemStatus: 'running' | 'frozen';
  setSystemStatus: (status: 'running' | 'frozen') => void;
  onConflictsInjected?: () => void | Promise<void>;
}

type InjectState = 'idle' | 'loading' | 'success' | 'error';

export function Sidebar({ activeTab, setActiveTab, systemStatus, setSystemStatus, onConflictsInjected }: SidebarProps) {
  const [injectState, setInjectState] = useState<InjectState>('idle');
  const [injectMsg, setInjectMsg] = useState<string>('');
  const [overrideLoading, setOverrideLoading] = useState(false);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'trains', label: 'Active Trains', icon: Train },
    { id: 'network', label: 'Network Map', icon: Map },
    { id: 'schedule', label: 'Schedule', icon: Calendar },
    { id: 'logs', label: 'System Logs', icon: Settings },
  ];

  const handleInjectConflicts = async () => {
    if (injectState === 'loading') return;
    setInjectState('loading');
    setInjectMsg('');
    try {
      const result = await api.injectSampleConflicts();
      if (onConflictsInjected) {
        await onConflictsInjected();
      }
      setInjectState('success');
      setInjectMsg(`✓ ${result.trains_affected} trains delayed`);
      setTimeout(() => {
        setInjectState('idle');
        setInjectMsg('');
      }, 3000);
    } catch (err: any) {
      setInjectState('error');
      setInjectMsg('Injection failed');
      setTimeout(() => {
        setInjectState('idle');
        setInjectMsg('');
      }, 3000);
    }
  };

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

      {/* ── Sample Conflict Injection ── */}
      <div className="px-4 pb-3">
        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <div className="flex items-center gap-2 text-xs font-medium text-amber-400/80 mb-2 uppercase tracking-wider">
            <Zap className="w-3.5 h-3.5" />
            Conflict Simulator
          </div>
          <p className="text-[11px] text-zinc-500 mb-3 leading-relaxed">
            Inject random delays & section conflicts so the optimizer has something to resolve.
          </p>
          <button
            id="inject-conflicts-btn"
            onClick={handleInjectConflicts}
            disabled={injectState === 'loading'}
            className={cn(
              "w-full py-2 px-3 rounded text-xs font-semibold transition-all duration-200 border flex items-center justify-center gap-1.5",
              injectState === 'idle' &&
              "bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border-amber-500/20 hover:border-amber-500/40",
              injectState === 'loading' &&
              "bg-amber-500/5 text-amber-500/50 border-amber-500/10 cursor-not-allowed",
              injectState === 'success' &&
              "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
              injectState === 'error' &&
              "bg-red-500/10 text-red-400 border-red-500/20",
            )}
          >
            {injectState === 'loading' && (
              <span className="w-3 h-3 border border-amber-400/50 border-t-amber-400 rounded-full animate-spin" />
            )}
            {injectState === 'success' && <CheckCircle className="w-3.5 h-3.5" />}
            {injectState === 'error' && <AlertTriangle className="w-3.5 h-3.5" />}
            {injectState === 'idle' && <Zap className="w-3.5 h-3.5" />}

            {injectState === 'idle' && 'Add Sample Conflicts'}
            {injectState === 'loading' && 'Injecting…'}
            {(injectState === 'success' || injectState === 'error') && injectMsg}
          </button>
        </div>
      </div>

      {/* ── Safety Net ── */}
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
            onClick={async () => {
              if (overrideLoading) return;
              setOverrideLoading(true);
              const newStatus = systemStatus === 'running' ? 'frozen' : 'running';
              try {
                const res = await fetch('http://localhost:8010/api/v1/override', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    enabled: newStatus === 'frozen',
                    reason: newStatus === 'frozen' ? 'Dispatcher manual override' : 'Resuming automated operations',
                  }),
                });
                if (res.ok) setSystemStatus(newStatus);
              } catch (err) {
                console.error('Override API call failed:', err);
              } finally {
                setOverrideLoading(false);
              }
            }}
            disabled={overrideLoading}
            className={cn(
              "w-full py-2 px-3 rounded text-xs font-semibold transition-colors border",
              systemStatus === 'running'
                ? "bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20"
                : "bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20",
              overrideLoading && "opacity-50 cursor-not-allowed"
            )}
          >
            {overrideLoading ? 'Processing...' : systemStatus === 'running' ? 'MANUAL OVERRIDE' : 'RESUME SYSTEM'}
          </button>
        </div>
      </div>
    </aside>
  );
}


