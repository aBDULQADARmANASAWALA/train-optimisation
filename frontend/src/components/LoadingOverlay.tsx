import { Train } from 'lucide-react';

interface LoadingOverlayProps {
    message: string;
}

export function LoadingOverlay({ message }: LoadingOverlayProps) {
    return (
        <div className="fixed inset-0 bg-zinc-950/80 backdrop-blur-sm z-[100] flex flex-col items-center justify-center gap-6 text-white">
            <div className="relative">
                <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                    <Train className="w-6 h-6 text-blue-500 animate-pulse" />
                </div>
            </div>
            <div className="flex flex-col items-center gap-2">
                <h2 className="text-xl font-bold tracking-widest uppercase text-blue-50">RailOrchestra</h2>
                <p className="text-sm font-mono text-blue-400 animate-pulse">{message}</p>
            </div>
        </div>
    );
}
