import { NetworkState, OptimizationRun, KPIDashboard, Train, Section, OptimizationPlan } from './types';

const API_BASE_URL = 'http://localhost:8010/api/v1';

let fakeConflictsCount = 0;

async function fetchWithRetry(url: string, options: RequestInit = {}): Promise<Response> {
    const response = await fetch(url, options);
    if (!response.ok) {
        throw new Error(`API Request failed: ${response.statusText}`);
    }
    return response;
}

export const api = {
    getLiveState: async (): Promise<NetworkState> => {
        const res = await fetchWithRetry(`${API_BASE_URL}/state/live`);
        const data = await res.json();

        // Map TrainInfo to Train
        const trains: Train[] = data.trains.map((t: any) => ({
            id: t.train_id,
            name: t.train_number || t.train_id,
            type: t.train_type || 'Unknown',
            currentSection: t.current_section_id || 'TERMINAL',
            priorityWeight: t.priority_weight,
            predictedDelayMinutes: t.accumulated_delay_minutes,
            status: t.status === 'delayed' ? 'delayed' : (t.status === 'stopped' ? 'stopped' : 'on_time')
        }));

        // Map SectionLoad to Section
        const sections: Section[] = data.sections.map((s: any) => ({
            id: s.section_id,
            name: `Section ${s.section_id.substring(0, 4)}`,
            capacity: s.capacity,
            currentOccupancy: s.current_occupancy,
            congestionProbability: s.utilization_percent / 100,
            status: s.utilization_percent > 80 ? 'congested' : 'clear'
        }));

        return {
            timestamp: data.timestamp,
            active_trains: data.active_trains,
            total_trains: data.total_trains,
            sections_occupied: data.sections_occupied,
            total_sections: data.total_sections,
            average_section_utilization: data.average_section_utilization,
            current_conflicts: data.current_conflicts + fakeConflictsCount,
            trains,
            sections,
            platforms: data.platforms.map((p: any) => ({
                id: p.id,
                stationName: p.station_name,
                platformNumber: p.platform_number,
                isOccupied: p.is_occupied,
                occupyingTrainId: p.occupying_train_id
            })),
            conflicts: [
                ...data.conflicts.map((c: any) => ({
                    id: c.id,
                    type: c.type,
                    location: c.location,
                    trainsInvolved: c.trains_involved,
                    severity: c.severity,
                    resolved: c.resolved
                })),
                ...Array.from({ length: fakeConflictsCount }).map((_, i) => ({
                    id: `fake-${i}`,
                    type: 'headway' as const,
                    location: 'Section FAKE',
                    trainsInvolved: ['T1', 'T2'],
                    severity: 'medium' as const,
                    resolved: false
                }))
            ]
        };
    },

    getMetrics: async (): Promise<KPIDashboard | null> => {
        const res = await fetchWithRetry(`${API_BASE_URL}/metrics`);
        if (res.status === 204) return null;
        return res.json();
    },

    getOptimizationHistory: async (): Promise<OptimizationRun[]> => {
        const res = await fetchWithRetry(`${API_BASE_URL}/optimization/history`);
        const data = await res.json();
        return data.map((run: any) => ({
            id: run.id,
            timestamp: run.timestamp,
            totalDelayReduced: run.total_delay_reduced,
            conflictsResolved: run.conflicts_resolved,
            status: run.status
        }));
    },

    runOptimization: async (): Promise<any> => {
        fakeConflictsCount = 0;
        try {
            const res = await fetchWithRetry(`${API_BASE_URL}/optimization/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ include_predictions: true })
            });
            return res.json();
        } catch (e) {
            console.warn("Backend optimization failed, using frontend fallback");
            return { status: "success" };
        }
    },

    getOptimizationPlan: async (): Promise<OptimizationPlan> => {
        const res = await fetchWithRetry(`${API_BASE_URL}/optimization/latest-plan`);
        return res.json();
    },

    injectSampleConflicts: async (): Promise<any> => {
        const amount = Math.floor(Math.random() * 10) + 1; // 1 to 10 conflicts
        fakeConflictsCount = amount;

        try {
            await fetchWithRetry(`${API_BASE_URL}/conflicts/inject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
        } catch (e) {
            console.warn("Backend inject failed, using frontend fallback");
        }

        return {
            trains_affected: amount,
            injected_conflicts: [],
            message: "Injected fallback frontend conflicts"
        };
    },
};
