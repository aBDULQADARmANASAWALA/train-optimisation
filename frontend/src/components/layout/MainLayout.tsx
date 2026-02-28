import React, { ReactNode } from 'react';

export interface MainLayoutProps {
    children?: ReactNode;
    onOptimize?: () => void;
    systemStatus?: 'connected' | 'disconnected' | 'error';
    sidebarOpen?: boolean;
    onToggleSidebar?: () => void;
}

/**
 * MainLayout Component
 * Provides responsive full-screen layout with header, sidebar, and main content area
 * No business logic - purely presentational
 */
export const MainLayout: React.FC<MainLayoutProps> = ({
    children,
    onOptimize,
    systemStatus = 'connected',
    sidebarOpen = true,
    onToggleSidebar,
}) => {
    const statusColors = {
        connected: 'bg-green-500',
        disconnected: 'bg-yellow-500',
        error: 'bg-red-500',
    };

    const statusText = {
        connected: 'System Connected',
        disconnected: 'System Disconnected',
        error: 'System Error',
    };

    return (
        <div className="flex flex-col h-screen w-full bg-slate-950 text-slate-50">
            {/* Header */}
            <header className="flex items-center justify-between h-16 px-6 bg-slate-900 border-b border-slate-800 shadow-lg">
                {/* Left Section - Logo and Title */}
                <div className="flex items-center gap-4">
                    <button
                        onClick={onToggleSidebar}
                        className="lg:hidden p-2 hover:bg-slate-800 rounded-md transition-colors"
                        aria-label="Toggle sidebar"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M4 6h16M4 12h16M4 18h16"
                            />
                        </svg>
                    </button>

                    <h1 className="text-xl font-bold text-cyan-400">Railway Control System</h1>
                </div>

                {/* Right Section - Status and Actions */}
                <div className="flex items-center gap-6">
                    {/* System Status Indicator */}
                    <div className="flex items-center gap-3 px-4 py-2 bg-slate-800 rounded-lg border border-slate-700">
                        <div
                            className={`w-3 h-3 rounded-full ${statusColors[systemStatus]} animate-pulse`}
                            aria-label={`System status: ${statusText[systemStatus]}`}
                        />
                        <span className="text-sm font-medium text-slate-300">{statusText[systemStatus]}</span>
                    </div>

                    {/* Run Optimization Button */}
                    <button
                        onClick={onOptimize}
                        className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white font-semibold rounded-lg transition-colors duration-200 shadow-md hover:shadow-lg flex items-center gap-2"
                        aria-label="Run optimization"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M13 10V3L4 14h7v7l9-11h-7z"
                            />
                        </svg>
                        <span className="hidden sm:inline">Optimize</span>
                    </button>
                </div>
            </header>

            {/* Main Container */}
            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <aside
                    className={`${sidebarOpen
                            ? 'translate-x-0 w-64 lg:w-80'
                            : '-translate-x-full w-64 lg:w-80 lg:translate-x-0'
                        } fixed lg:relative lg:block h-full bg-slate-900 border-r border-slate-800 transition-transform duration-300 ease-in-out z-40 overflow-y-auto`}
                >
                    {/* Sidebar Header */}
                    <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800">
                        <h2 className="font-semibold text-slate-200">Controls</h2>
                        <button
                            onClick={onToggleSidebar}
                            className="lg:hidden p-2 hover:bg-slate-800 rounded-md"
                            aria-label="Close sidebar"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {/* Sidebar Content Placeholder */}
                    <div className="p-6 space-y-4">
                        <div className="space-y-2">
                            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
                                Placeholder
                            </h3>
                            <p className="text-sm text-slate-400">
                                Future controls and filters will be placed here
                            </p>
                        </div>

                        {/* Example placeholder sections */}
                        <div className="space-y-3 pt-4">
                            <div className="p-3 bg-slate-800 border border-slate-700 rounded-lg">
                                <p className="text-xs text-slate-400">Control Panel 1</p>
                            </div>
                            <div className="p-3 bg-slate-800 border border-slate-700 rounded-lg">
                                <p className="text-xs text-slate-400">Control Panel 2</p>
                            </div>
                        </div>
                    </div>
                </aside>

                {/* Overlay for mobile when sidebar is open */}
                {sidebarOpen && (
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 lg:hidden z-30"
                        onClick={onToggleSidebar}
                        aria-hidden="true"
                    />
                )}

                {/* Main Content Area */}
                <main className="flex-1 overflow-auto bg-slate-950">
                    <div className="h-full">
                        {children || (
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center">
                                    <p className="text-slate-400 mb-2">Main Content Area</p>
                                    <p className="text-slate-500 text-sm">Ready for dashboard components</p>
                                </div>
                            </div>
                        )}
                    </div>
                </main>
            </div>
        </div>
    );
};

export default MainLayout;
