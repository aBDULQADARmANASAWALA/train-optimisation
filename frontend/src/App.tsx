import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { TrainList } from './components/TrainList';
import { NetworkMap } from './components/NetworkMap';
import { ScheduleView } from './components/ScheduleView';
import { LogsView } from './components/LogsView';
import { LiveDataProvider, useLiveData } from './context/LiveDataContext';
import { LoadingOverlay } from './components/LoadingOverlay';

function AppLayout() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [systemStatus, setSystemStatus] = useState<'running' | 'frozen'>('running');
  const { loading, refreshData } = useLiveData();

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'trains':
        return <TrainList />;
      case 'network':
        return <NetworkMap />;
      case 'schedule':
        return <ScheduleView />;
      case 'logs':
        return <LogsView />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <>
      {loading && <LoadingOverlay message="Syncing with backend..." />}
      <div className="flex h-screen bg-zinc-50 font-sans text-zinc-900 overflow-hidden">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          systemStatus={systemStatus}
          setSystemStatus={setSystemStatus}
          onConflictsInjected={() => refreshData(true)}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <Header systemStatus={systemStatus} />
          <main className="flex-1 overflow-y-auto">
            {renderContent()}
          </main>
        </div>
      </div>
    </>
  );
}


export default function App() {
  return (
    <LiveDataProvider>
      <AppLayout />
    </LiveDataProvider>
  );
}
