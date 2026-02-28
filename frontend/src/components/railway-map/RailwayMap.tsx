import React, { useCallback, useMemo } from 'react';
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

// ============================================================================
// TypeScript Interfaces
// ============================================================================

export interface Station {
    id: string;
    name: string;
    location: {
        lat: number;
        lng: number;
    };
    platforms: number;
    capacity: number;
}

export interface Section {
    id: string;
    name: string;
    fromStationId: string;
    toStationId: string;
    length: number;
    speedLimit: number;
    trackType: 'single' | 'double' | 'multiple';
    occupiedTrackCount: number;
}

export interface SectionLoad {
    sectionId: string;
    occupancyRate: number;
    trainCount: number;
}

export interface Conflict {
    id: string;
    trainIds: string[];
    sectionId: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    estimatedResolutionTime: number;
    description: string;
}

export interface RailwayMapProps {
    stations: Station[];
    sections: Section[];
    sectionLoads: Record<string, SectionLoad>;
    conflicts: Conflict[];
    onStationClick?: (stationId: string) => void;
    onSectionClick?: (sectionId: string) => void;
}

// ============================================================================
// Custom Nodes
// ============================================================================

const StationNode: React.FC<{ data: any; }> = ({ data }) => {
    const hasConflict = data.hasConflict || false;
    const borderColor = hasConflict ? 'border-red-500' : 'border-cyan-400';
    const bgColor = hasConflict ? 'bg-red-900' : 'bg-slate-800';

    return (
        <div
            className={`px-4 py-2 rounded-lg border-2 ${borderColor} ${bgColor} text-slate-50 shadow-lg cursor-pointer hover:shadow-xl transition-shadow`}
            title={data.tooltip}
        >
            <div className="font-semibold text-sm">{data.name}</div>
            <div className="text-xs text-slate-400">P:{data.platforms}</div>
        </div>
    );
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get color based on section occupancy rate (0-1)
 */
const getCongestionColor = (occupancyRate: number): string => {
    if (occupancyRate >= 0.9) return '#ef4444'; // red
    if (occupancyRate >= 0.7) return '#f97316'; // orange
    if (occupancyRate >= 0.5) return '#eab308'; // yellow
    return '#22c55e'; // green
};

/**
 * Get stroke width based on track type
 */
const getStrokeWidth = (trackType: 'single' | 'double' | 'multiple'): number => {
    switch (trackType) {
        case 'single':
            return 2;
        case 'double':
            return 3;
        case 'multiple':
            return 4;
        default:
            return 2;
    }
};

/**
 * Calculate layout positions using a simple circular layout
 * Can be replaced with a more sophisticated algorithm (e.g., Dagre)
 */
const calculateNodePositions = (stationCount: number): Record<string, { x: number; y: number; }> => {
    const positions: Record<string, { x: number; y: number; }> = {};
    const radius = 300;
    const centerX = 500;
    const centerY = 300;

    // Arrange stations in a circle
    for (let i = 0; i < stationCount; i++) {
        const angle = (i / stationCount) * 2 * Math.PI;
        positions[i.toString()] = {
            x: centerX + radius * Math.cos(angle),
            y: centerY + radius * Math.sin(angle),
        };
    }

    return positions;
};

// ============================================================================
// RailwayMap Component
// ============================================================================

const RailwayMap: React.FC<RailwayMapProps> = React.memo(
    ({
        stations,
        sections,
        sectionLoads,
        conflicts,
        onStationClick,
        onSectionClick,
    }) => {
        // Build conflict lookup for O(1) access
        const conflictsBySection = useMemo(() => {
            const map = new Map<string, Conflict>();
            conflicts.forEach((conflict) => {
                map.set(conflict.sectionId, conflict);
            });
            return map;
        }, [conflicts]);

        // Build station index
        const stationIndex = useMemo(() => {
            const index = new Map<string, number>();
            stations.forEach((station, idx) => {
                index.set(station.id, idx);
            });
            return index;
        }, [stations]);

        // Calculate positions
        const positions = useMemo(() => calculateNodePositions(stations.length), [stations.length]);

        // Create nodes from stations
        const nodes: Node[] = useMemo(() => {
            return stations.map((station, idx) => {
                const hasConflict = Array.from(conflictsBySection.values()).some((c) =>
                    c.trainIds.some((trainId) => trainId === station.id)
                );

                return {
                    id: station.id,
                    data: {
                        label: <StationNode data={{ ...station, hasConflict, tooltip: `${station.name}\nPlatforms: ${station.platforms}\nCapacity: ${station.capacity}` }} />,
                        hasConflict,
                        name: station.name,
                        platforms: station.platforms,
                    },
                    position: positions[idx.toString()] || { x: 0, y: 0 },
                    style: {
                        background: 'transparent',
                        border: 'none',
                        padding: 0,
                    },
                };
            });
        }, [stations, conflictsBySection, positions]);

        // Create edges from sections
        const edges: Edge[] = useMemo(() => {
            return sections.map((section) => {
                const load = sectionLoads[section.id];
                const occupancyRate = load?.occupancyRate ?? 0;
                const conflict = conflictsBySection.get(section.id);
                const color = conflict ? '#ef4444' : getCongestionColor(occupancyRate);
                const strokeWidth = getStrokeWidth(section.trackType);

                const tooltip = `${section.name}\nOccupancy: ${Math.round(occupancyRate * 100)}%\nTrains: ${load?.trainCount ?? 0}\nSpeed Limit: ${section.speedLimit} km/h`;

                return {
                    id: section.id,
                    source: section.fromStationId,
                    target: section.toStationId,
                    style: {
                        stroke: color,
                        strokeWidth: strokeWidth + (conflict ? 2 : 0),
                        transition: 'stroke 0.3s ease',
                    },
                    data: {
                        tooltip,
                        occupancyRate,
                        conflict: !!conflict,
                    },
                };
            });
        }, [sections, sectionLoads, conflictsBySection]);

        // React Flow state
        const [flowNodes, setNodes, onNodesChange] = useNodesState(nodes);
        const [flowEdges, setEdges, onEdgesChange] = useEdgesState(edges);

        // Update nodes when data changes
        React.useEffect(() => {
            setNodes(nodes);
        }, [nodes, setNodes]);

        // Update edges when data changes
        React.useEffect(() => {
            setEdges(edges);
        }, [edges, setEdges]);

        // Handle node clicks
        const onNodeClick = useCallback(
            (_event: any, node: Node) => {
                onStationClick?.(node.id);
            },
            [onStationClick]
        );

        // Handle edge clicks
        const onEdgeClick = useCallback(
            (_event: any, edge: Edge) => {
                onSectionClick?.(edge.id);
            },
            [onSectionClick]
        );

        return (
            <div className="w-full h-full">
                <ReactFlow
                    nodes={flowNodes}
                    edges={flowEdges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={onNodeClick}
                    onEdgeClick={onEdgeClick}
                    fitView
                >
                    <Background color="#1e293b" gap={16} />
                    <Controls position="top-left" />
                </ReactFlow>

                {/* Legend */}
                <div className="absolute bottom-6 right-6 bg-slate-900 border border-slate-700 rounded-lg p-4 shadow-lg max-w-xs">
                    <h3 className="font-semibold text-slate-200 mb-3 text-sm">Legend</h3>
                    <div className="space-y-2 text-xs text-slate-400">
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-1 bg-green-500" />
                            <span>{'<50% Occupancy'}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-1 bg-yellow-500" />
                            <span>50-70% Occupancy</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-1 bg-orange-500" />
                            <span>70-90% Occupancy</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-1 bg-red-500" />
                            <span>{'>90% or Conflict'}</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    }
);

RailwayMap.displayName = 'RailwayMap';

export default RailwayMap;
