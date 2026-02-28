import axios, {
    AxiosInstance,
    AxiosError,
    InternalAxiosRequestConfig,
    AxiosResponse,
} from 'axios';
import { LiveState } from '../features/state/stateSlice';
import { OptimizationResult, OptimizationConfig } from '../features/optimization/optimizationSlice';
import { KPIData } from '../features/kpi/kpiSlice';
import { Override, OverrideRequest } from '../app/slices/overrideSlice';

// API Error types
export interface ApiError {
    status: number;
    message: string;
    code?: string;
    details?: Record<string, unknown>;
}

export class ApiErrorHandler extends Error implements ApiError {
    status: number;
    code?: string;
    details?: Record<string, unknown>;

    constructor(error: AxiosError<any>) {
        const status = error.response?.status || 0;
        const message = error.response?.data?.message || error.message;
        const code = error.response?.data?.code;
        const details = error.response?.data?.details;

        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.code = code;
        this.details = details;
    }
}

// Create Axios instance
const baseURL = (import.meta.env as any).VITE_API_BASE_URL || 'http://localhost:8000/api';

const axiosInstance: AxiosInstance = axios.create({
    baseURL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor
axiosInstance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        // Add request timestamp for tracking
        config.headers['X-Request-ID'] = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        return config;
    },
    (error: AxiosError) => {
        return Promise.reject(error);
    }
);

// Response interceptor
axiosInstance.interceptors.response.use(
    (response: AxiosResponse) => {
        return response;
    },
    (error: AxiosError) => {
        // Handle 401 Unauthorized - clear auth token
        if (error.response?.status === 401) {
            localStorage.removeItem('auth_token');
            // Dispatch logout event or trigger re-authentication
            window.dispatchEvent(new CustomEvent('auth:unauthorized'));
        }

        // Convert to ApiError
        return Promise.reject(new ApiErrorHandler(error));
    }
);

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch live railway state (trains, signals, track sections)
 */
export const fetchLiveState = async (): Promise<LiveState> => {
    try {
        const response = await axiosInstance.get<LiveState>('/state/live');
        return response.data;
    } catch (error) {
        throw error instanceof ApiErrorHandler ? error : new Error('Failed to fetch live state');
    }
};

/**
 * Run optimization with specified configuration
 */
export const runOptimization = async (config: OptimizationConfig): Promise<OptimizationResult> => {
    try {
        const response = await axiosInstance.post<OptimizationResult>('/optimization/run', config);
        return response.data;
    } catch (error) {
        throw error instanceof ApiErrorHandler ? error : new Error('Failed to run optimization');
    }
};

/**
 * Fetch KPI metrics and aggregations
 */
export const fetchKPIs = async (): Promise<KPIData> => {
    try {
        const response = await axiosInstance.get<KPIData>('/metrics');
        return response.data;
    } catch (error) {
        throw error instanceof ApiErrorHandler ? error : new Error('Failed to fetch KPI metrics');
    }
};

/**
 * Send override decision to backend
 */
export const sendOverrideDecision = async (overrideRequest: OverrideRequest): Promise<Override> => {
    try {
        const response = await axiosInstance.post<Override>('/override', overrideRequest);
        return response.data;
    } catch (error) {
        throw error instanceof ApiErrorHandler ? error : new Error('Failed to apply override');
    }
};

/**
 * Revoke an existing override
 */
export const revokeOverride = async (overrideId: string): Promise<Override> => {
    try {
        const response = await axiosInstance.delete<Override>(`/override/${overrideId}`);
        return response.data;
    } catch (error) {
        throw error instanceof ApiErrorHandler ? error : new Error('Failed to revoke override');
    }
};

/**
 * Health check endpoint
 */
export const checkHealth = async (): Promise<{ status: string; timestamp: number; }> => {
    try {
        const response = await axiosInstance.get<{ status: string; timestamp: number; }>('/health');
        return response.data;
    } catch (error) {
        throw error instanceof ApiErrorHandler ? error : new Error('Health check failed');
    }
};

export default axiosInstance;
