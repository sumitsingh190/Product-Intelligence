import axios, { type AxiosInstance, type AxiosResponse } from "axios";
import { useAuthStore } from "../store/authStore";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api: AxiosInstance = axios.create({
    baseURL: `${BASE_URL}/api/v1`,
    headers: {
        "Content-Type": "application/json",
    },
    timeout: 30000,
});

// Attach token to every request
api.interceptors.request.use((config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Handle 401 auto-logout

api.interceptors.response.use(
    (response: AxiosResponse) => response,
    async (error) => {
        if (error.response?.status === 401) {
            useAuthStore.getState().logout();
            window.location.href="/login";
        }
        return Promise.reject(error);
    }
);

export const authApi = {
    register: (data: { email: string; full_name: string; password: string }) =>
        api.post("/auth/register", data),
    login: (data: { email: string; password: string }) =>
        api.post("/auth/login", data),
    refresh: (refreshToken: string) =>
        api.post("/auth/refresh", { refresh_token: refreshToken }),
    me: () => api.get("/auth/me"),
    logout: () => api.post("/auth/logout"),
};
// Workspaces (Workspace is the sole tenant boundary)

export const workspacesApi = {
    create: (data: { name: string; workspace_type?: string; description?: string}) =>
        api.post("/workspaces", data),
    list: (page = 1, pageSize = 20) =>
        api.get("/workspaces", {params: {page, page_size: pageSize } }),
    get: (id: string) => api.get(`/workspaces/${id}`),
    current: () => api.get("/workspaces/current"),
};

// Data Sources
export const dataSourcesApi = {
    list: (workspaceId: string) =>
        api.get("/data-sources", {params: { workspace_id: workspaceId }}),
    create: (
        workspaceId: string,
        data: { name: string; source_type: string; config: Record<string, unknown>; sync_interval_seconds?: number } 
    )=> api.post("/data-sources", data, {params: {workspace_id: workspaceId}}),
    update: (
        id: string,
        data: { name?: string; config?: Record<string, unknown>; status?: string; sync_interval_seconds?: number }
    ) => api.patch(`/data-sources/${id}`, data),
    
    delete: (id: string) => api.delete(`/data-sources/${id}`),
    test: (id: string) => api.post(`/data-sources/${id}/test`),
    sync: (id: string) => api.post(`/data-sources/${id}/sync`),
    uploadCsv: (workspaceId: string, name: string, kind: string, file: File) => {
        const form = new FormData();
        form.append("name", name);
        form.append("kind", kind);
        form.append("file", file);
        return api.post("/data-sources/upload-csv", form, {
            params: { workspace_id: workspaceId },
            headers: { "Content-Type": "multipart/form-data"}, 
        });
    },
};

// Insights
export const insightsApi = {
    list: (
        workspaceId: string,
        filters?: {insight_type?: string; severity?: string; status?: string; page?: number} 
    ) => api.get("/insights", { params: { workspace_id: workspaceId, ...filters}}),
    get: (id: string) => api.get(`/insights/${id}`),
    updateStatus: (id: string, status: string) =>
        api.patch(`/insights/${id}/status`, {status}),
    triggerAnalysis: (workspaceId: string) =>
        api.post("/insights/analyze", null, { params: { workspace_id: workspaceId} }),
};

export const recommendationsApi = {
    list: (
        workspaceId: string,
        filters?: { recommendation_type?: string; status?: string; min_roi_score?: number; page?: number } 
    ) => api.get("/recommendations", {params: {workspace_id: workspaceId, ...filters } }), 
    get: (id: string) => api.get(`/recommendations/${id}`),
    updateStatus: (id: string, status: string) =>
        api.patch(`/recommendations/${id}/status`, {status}),
    generate: (workspaceId: string) =>
        api.post("/recommendations/generate", null, {params: { workspace_id: workspaceId }}), 
    decide: (id: string, decision: string, reason?: string) => 
        api.post(`/recommendations/${id}/decision`, {decision, reason }),
    decisions: (workspaceId: string, limit = 100) =>
        api.get("/recommendations/decisions/log", { params: {workspace_id: workspaceId, limit}, }),
};

// Reports
export const reportsApi = {
    list: (workspaceId: string, page = 1) =>
        api.get("/reports", {params: {workspace_id: workspaceId, page}}), 
    get: (id: string) => api.get(`/reports/${id}`), 
    generate: (workspaceId: string, reportType: string, recommendationId?: string) => 
        api.post("/reports/generate", null, {
            params: {
                workspace_id: workspaceId, 
                report_type: reportType, 
                ...(recommendationId? {recommendation_id: recommendationId }: {}),
            }
        }),
    export: (id: string, format: "markdown" | "pdf" | "html" = "markdown") =>
        api.get(`/reports/${id}/export`, { params: { format }, responseType: "blob" }), 
};

// Analytics KPIs and trend history
export const analyticsApi = {
    kpis: (workspaceId: string) =>
        api.get("/analytics/kpis", {params: { workspace_id: workspaceId} }), 
    history: (workspaceId: string, metricName: string, days = 90) =>
        api.get(`/analytics/kpis/${metricName}/history`, {
            params: { workspace_id: workspaceId, days },
        }),
    snapshot: (workspaceId: string) =>
        api.post("/analytics/kpis/snapshot", null, { params: { workspace_id: workspaceId }}), 
};


// Semantic search (Phase C)
export const searchApi = {
    query: (workspaceId: string, q: string, topK = 10) =>
        api.get("/search", { params: { workspace_id: workspaceId, q, top_k: topK } }),
};