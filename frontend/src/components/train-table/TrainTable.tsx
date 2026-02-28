import React, { useMemo, useState } from 'react';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface Train {
    id: string;
    name: string;
    status: 'on-time' | 'delayed' | 'at-station' | 'departed' | 'cancelled';
    currentLocationId: string;
    currentLocationName: string;
    scheduledDeparture: number;
    actualDeparture?: number;
    estimatedArrival: number;
    destination: string;
    passengers: number;
    capacity: number;
    platform?: string;
    delayMinutes: number;
}

export interface TrainTableProps {
    trains: Train[];
    onTrainSelect?: (trainId: string) => void;
    onTrainClick?: (train: Train) => void;
    loading?: boolean;
    highlightDelayed?: boolean;
}

type SortField = 'name' | 'status' | 'currentLocationName' | 'delayMinutes' | 'id';
type SortDirection = 'asc' | 'desc';

// ============================================================================
// TableHeader Component
// ============================================================================

interface TableHeaderProps {
    field: SortField;
    label: string;
    sortField: SortField;
    sortDirection: SortDirection;
    onSort: (field: SortField) => void;
}

const TableHeader: React.FC<TableHeaderProps> = ({
    field,
    label,
    sortField,
    sortDirection,
    onSort,
}) => {
    const isActive = field === sortField;
    const icon = isActive ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅';

    return (
        <th
            className={`px-4 py-3 text-left text-sm font-semibold cursor-pointer select-none transition-colors ${isActive
                    ? 'bg-cyan-900 text-cyan-100 border-b-2 border-cyan-400'
                    : 'bg-slate-800 text-slate-300 border-b border-slate-700 hover:bg-slate-700'
                }`}
            onClick={() => onSort(field)}
        >
            <div className="flex items-center gap-2">
                <span>{label}</span>
                <span className="text-xs opacity-70">{icon}</span>
            </div>
        </th>
    );
};

// ============================================================================
// TrainRow Component
// ============================================================================

interface TrainRowProps {
    train: Train;
    isDelayed: boolean;
    onSelect?: (trainId: string) => void;
    onClick?: (train: Train) => void;
}

const TrainRow: React.FC<TrainRowProps> = React.memo(
    ({ train, isDelayed, onSelect, onClick }) => {
        const statusColors = {
            'on-time': 'text-green-400 bg-green-900/20',
            delayed: 'text-orange-400 bg-orange-900/20',
            'at-station': 'text-blue-400 bg-blue-900/20',
            departed: 'text-cyan-400 bg-cyan-900/20',
            cancelled: 'text-red-400 bg-red-900/20',
        };

        const rowBgColor = isDelayed ? 'bg-red-900/30 hover:bg-red-900/40' : 'hover:bg-slate-800/50';

        return (
            <tr
                className={`border-b border-slate-700 transition-colors cursor-pointer ${rowBgColor}`}
                onClick={() => onClick?.(train)}
            >
                {/* Train ID */}
                <td className="px-4 py-3 text-sm font-medium text-slate-300">{train.id}</td>

                {/* Priority / Status Badge */}
                <td className="px-4 py-3 text-sm">
                    <span
                        className={`px-2 py-1 rounded font-medium text-xs ${statusColors[train.status]
                            }`}
                    >
                        {train.status.charAt(0).toUpperCase() + train.status.slice(1).replace('-', ' ')}
                    </span>
                </td>

                {/* Current Location */}
                <td className="px-4 py-3 text-sm text-slate-400">{train.currentLocationName}</td>

                {/* Delay Minutes */}
                <td
                    className={`px-4 py-3 text-sm font-semibold ${isDelayed ? 'text-red-400' : 'text-green-400'
                        }`}
                >
                    {train.delayMinutes > 0 ? `+${train.delayMinutes}m` : 'On time'}
                </td>

                {/* Destination */}
                <td className="px-4 py-3 text-sm text-slate-400 truncate">{train.destination}</td>

                {/* Occupancy */}
                <td className="px-4 py-3 text-sm text-slate-400">
                    {Math.round((train.passengers / train.capacity) * 100)}%
                </td>

                {/* Platform */}
                <td className="px-4 py-3 text-sm text-slate-400">
                    {train.platform ? `P${train.platform}` : '-'}
                </td>

                {/* Select Checkbox */}
                <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                        type="checkbox"
                        className="w-4 h-4 cursor-pointer accent-cyan-500"
                        onChange={() => onSelect?.(train.id)}
                        aria-label={`Select train ${train.id}`}
                    />
                </td>
            </tr>
        );
    }
);

TrainRow.displayName = 'TrainRow';

// ============================================================================
// TrainTable Component
// ============================================================================

const TrainTable: React.FC<TrainTableProps> = React.memo(
    ({ trains, onTrainSelect, onTrainClick, loading = false, highlightDelayed = true }) => {
        const [sortField, setSortField] = useState<SortField>('id');
        const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

        // Handle column sort
        const handleSort = (field: SortField) => {
            if (sortField === field) {
                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
            } else {
                setSortField(field);
                setSortDirection('asc');
            }
        };

        // Sort trains
        const sortedTrains = useMemo(() => {
            const sorted = [...trains].sort((a, b) => {
                let aValue: any = a[sortField];
                let bValue: any = b[sortField];

                // Handle numeric comparisons
                if (typeof aValue === 'number' && typeof bValue === 'number') {
                    return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
                }

                // Handle string comparisons
                aValue = String(aValue).toLowerCase();
                bValue = String(bValue).toLowerCase();

                if (sortDirection === 'asc') {
                    return aValue.localeCompare(bValue);
                } else {
                    return bValue.localeCompare(aValue);
                }
            });

            return sorted;
        }, [trains, sortField, sortDirection]);

        return (
            <div className="w-full h-full flex flex-col bg-slate-950 rounded-lg border border-slate-800 shadow-lg overflow-hidden">
                {/* Table Header */}
                <div className="flex-shrink-0">
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse">
                            <thead>
                                <tr>
                                    <TableHeader
                                        field="id"
                                        label="Train ID"
                                        sortField={sortField}
                                        sortDirection={sortDirection}
                                        onSort={handleSort}
                                    />
                                    <TableHeader
                                        field="status"
                                        label="Status"
                                        sortField={sortField}
                                        sortDirection={sortDirection}
                                        onSort={handleSort}
                                    />
                                    <TableHeader
                                        field="currentLocationName"
                                        label="Current Location"
                                        sortField={sortField}
                                        sortDirection={sortDirection}
                                        onSort={handleSort}
                                    />
                                    <TableHeader
                                        field="delayMinutes"
                                        label="Delay"
                                        sortField={sortField}
                                        sortDirection={sortDirection}
                                        onSort={handleSort}
                                    />
                                    <th className="px-4 py-3 text-left text-sm font-semibold bg-slate-800 text-slate-300 border-b border-slate-700">
                                        Destination
                                    </th>
                                    <th className="px-4 py-3 text-left text-sm font-semibold bg-slate-800 text-slate-300 border-b border-slate-700">
                                        Occupancy
                                    </th>
                                    <th className="px-4 py-3 text-left text-sm font-semibold bg-slate-800 text-slate-300 border-b border-slate-700">
                                        Platform
                                    </th>
                                    <th className="px-4 py-3 text-center text-sm font-semibold bg-slate-800 text-slate-300 border-b border-slate-700 w-12">
                                        Select
                                    </th>
                                </tr>
                            </thead>
                        </table>
                    </div>
                </div>

                {/* Table Body */}
                <div className="flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-slate-400">
                                <div className="animate-spin inline-block w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full mb-2" />
                                <p className="text-sm">Loading trains...</p>
                            </div>
                        </div>
                    ) : sortedTrains.length === 0 ? (
                        <div className="flex items-center justify-center h-full">
                            <p className="text-slate-400">No trains available</p>
                        </div>
                    ) : (
                        <table className="w-full border-collapse">
                            <tbody>
                                {sortedTrains.map((train) => (
                                    <TrainRow
                                        key={train.id}
                                        train={train}
                                        isDelayed={highlightDelayed && train.delayMinutes > 0}
                                        onSelect={onTrainSelect}
                                        onClick={onTrainClick}
                                    />
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Footer - Row count */}
                {!loading && (
                    <div className="flex-shrink-0 px-4 py-2 bg-slate-900 border-t border-slate-800 text-xs text-slate-400">
                        Showing {sortedTrains.length} train{sortedTrains.length !== 1 ? 's' : ''}
                    </div>
                )}
            </div>
        );
    }
);

TrainTable.displayName = 'TrainTable';

export default TrainTable;
