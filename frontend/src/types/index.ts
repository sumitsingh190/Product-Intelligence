export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    pages: number;
}


export interface User {
    id: string;
    email: string;
    full_name: string;
    avatar_url?: string;
    is_active: boolean;
    is_verified: boolean;
    workspace_id?: string;
    role: string;
    created_at: string;
    updated_at: string;
}

export interface Workspace {
    id: string;
    name: string;
    slug: string;
    description?: string;
    workspace_type: string;
    is_active: boolean;
    config: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export type InsightType = "customer_feedback" | "engineering" | "analytics" | "competitor" | "product_health";
export type InsightSeverity = "critical" | "high" | "medium" | "low" | "info";
export type InsightStatus = "new" | "acknowledged" | "in_progress" | "resolved" | "dismissed";

export interface Insight {
    id: string;
    title: string
    summary: string;
    detail?: string;
    insight_type: InsightType;
    severity: InsightSeverity;
    status: InsightStatus;
    confidence_score: number;
    affected_users_estimate?: number;
    evidence: unknown[];
    tags: string[];
    workspace_id: string
    ai_metadata: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export type RecommendationType = "feature" | "bug fix" | "performance" | "ux" | "security" | "tech_debt" | "research" 
export type RecommendationStatus = "new" | "accepted" | "rejected" | "in_progress" | "completed" | "deferred"

export interface Recommendation {
    id: string;
    title: string;
    description: string;
    rationale?: string;
    recommendation_type: RecommendationType;
    status: RecommendationStatus;
    impact_score: number;
    effort_score: number;
    confidence_score: number;
    roi_score: number;
    priority_rank: number;
    estimated_effort_days?: number;
    estimated_users_impacted?: number;
    estimated_revenue_impact?: number;
    evidence: unknown[];
    insight_ids: string[];
    tags: string[];
    acceptance_criteria: unknown[];
    workspace_id: string;
    ai_metadata: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export interface Document {
    id: string;
    title: string;
    content: string;
    content_preview?: string;
    document_type: string;
    status: string;
    version: number;
    word_count: number;
    workspace_id: string;
    created_at: string;
    updated_at: string;
}

export interface DataSource {
    id: string;
    name: string;
    source_type: string;
    status: string;
    workspace_id: string;
    last_synced_at?: string;
    total_records_synced: number;
    created_at: string;
    updated_at: string;
}

export interface KPI {
    metric_name: string;
    current_value: number;
    previous_value: number | null;
    change_percent: number | null;
    period: string;
    unit: string;
    trend: "up" | "down" | "stable" | "new";
}

export interface KPIHistoryPoint {
    snapshot_date: string;
    metric_value: number;
}

export interface SearchResult {
    id: string;
    title: string;
    content_preview?: string;
    document_type?: string;
    similarity?: number;
    keyword_score?: number;
}

export interface AgentDecision {
    id: string;
    workspace_id: string;
    recommendation_id: string;
    decided_by_user_id?: string | null;
    decision: string;
    reason?: string | null;
    snapshot: Record<string, unknown>;
    created_at: string;
}