import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query":
import { Lightbulb, RefreshCw, Loader2 } from "lucide-react";
import { insightsApi } from "@/lib/api";
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";

import { cn, severityColor, statusColor, formatRelativeTime } from "@/lib/utils"; 
import type { Insight, InsightSeverity, InsightStatus, InsightType } from "@/types";

export function InsightsPage() {
    const qc = useQueryClient();
    const workspaceId = useCurrentWorkspaceId();
    const ready = !!workspaceId;
    const [typeFilter, setTypeFilter] = useState<InsightType | "">("");
    const [severityFilter, setSeverityFilter] = useState<InsightSeverity | "">("");
    const [statusFilter, setStatusFilter] = useState<InsightStatus | "">("");
    const [page, setPage] = useState(1);

    const {data, isLoading} = useQuery({
        queryKey: ["insights", workspaceId, typeFilter, severityFilter, statusFilter, page], 
        queryFn: () =>
            insightsApi.list(workspaceId!, { 
                insight_type: typeFilter || undefined,
                severity: severityFilter || undefined, 
                status: statusFilter || undefined, 
                page, 
            }), 
        select: (res) => res.data, 
        enabled: ready, 
    });

    const triggerAnalysis = useMutation({
        mutationFn: () => insightsApi.triggerAnalysis(workspaceId!),
        onSuccess: () => qc.invalidateQueries({queryKey: ["insights"] }), 
    });

    const updateStatus = useMutation({
        mutationFn: ({ id, status }: { id: string; status: string }) =>
            insightsApi.updateStatus( id, status),
        onSuccess: () => qc.invalidateQueries({queryKey: ["insights"]}), 
    });

    return (
        <div className="space-y-6">
            <div className = "flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Insights</h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        AI-generated product Intelligence from all data sources.
                    </p>
                </div>
                <button
                    onclick={() => triggerAnalysis.mutate()}
                    disabled={triggerAnalysis.isPending}
                    className "flex items-center gap-2 rounded-lg bg-primary, px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                    {triggerAnalysis.isPending? (
                        <Loader2 className "h-4 w-4 animate-spin" />
                    ) : (
                        <RefreshCw className="h-4 w-4" />
                    )}
                    Run Analysis
                </button>
            </div>

            /* Filters */

            <div className="flex flex-wrap gap-3">
                <select
                    value={typeFilter}
                    onChange={(e) => { setTypeFilter(e.target.value as InsightType | ""); setPage(1); }} 
                    className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm"
                >
                    <option value="">All Types</option>
                    <option value="customer feedback">Customer Feedback</option>
                    <option value="engineering">Engineering</option>
                    <option value="analytics">Analytics</option>
                    <option value="competitor">Competitor</option>
                    <option value="product health">Product Health</option>
                </select>
                <select
                    value={severityFilter}
                    onchange={(e) => { setSeverityFilter(e.target.value as InsightSeverity | ""); setPage(1); }} 
                    className = "rounded-lg border border-input bg-background px-3 py-1.5 text-sm"
                >
                    <option value="">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                    <option value="info">Info</option>
                </select>
                <select
                    value={statusFilter}
                    onChange={(e) => { setStatusFilter(e.target.value as InsightStatus | ""); setPage(1); }}
                    className = "rounded-lg border border-input bg-background px-3 py-1.5 text-sm"
                >
                    <option value="">All Statuses</option>
                    <option value="new">New</option>
                    <option value="acknowledged">Acknowledged</option> 
                    <option value="in progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                    <option value="dismissed">Dismissed</option>
                </select>
            </div>

            /* Insights list */

            {isLoading? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <div className="space-y-3">
                    {data?.items.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-border p-12 text-center">
                            <Lightbulb className="mx-auto mb-3 h-8 w-8 text-muted foreground" />
                            <p className="font-medium">No insights found</p>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Run an analysis to generate insights from your connected data sources.
                            </p>
                        </div>
                    ) : (
                        data?.items.map((insight: Insight) => (
                            <div key={insight.id} className="rounded-xl border border-border bg-card p-5">
                                <div className="flex items-start justify-between gap-4">\
                                    <div className="flex-1 min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", severityColor(insight.severity))}>
                                                {insight.severity}
                                            </span>
                                            <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", statusColor(insight.status))}>
                                                {insight.status.replace("_", " ")}
                                            </span>
                                            <span className="text-xs text-muted-foreground capitalize">
                                                {insight.insight_type.replace("_"," ")}
                                            </span>
                                        </div>
                                        <h3 className="mt-2 font-semibold">{insight.title}</h3>
                                        <p className="mt-1 text-sm text-muted-foreground">{insight.summary}</p>
                                        <div className="mt-3 flex flex-wrap gap-1.5">
                                            {insight.tags.map((tag) => (
                                                <span key={tag} className="rounded-full bg-accent px-2 py-0.5 text-xs">
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <div className = "flex shrink-0 flex-col items-end gap-2">
                                        <p className="text-xs text-muted foreground">{formatRelativeTime(insight.created_at))</p>
                                        <p className="text-xs text-muted-foreground">
                                            Confidence: {(insight.confidence_score * 100).toFixed(0)}%
                                        </p>
                                        {insight.status === "new" && (
                                            <button
                                                onclick={() => updateStatus.mutate({ id: insight.id, status: "acknowledged" })}
                                                className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium hover:bg-accent/80"
                                            >
                                                Acknowledge
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}

                    /* Pagination */

                    {data && data.pages > 1 && (
                        <div className="flex items-center justify-center gap-2 pt-2">
                            <button
                                disabled = {page === 1}
                                onClick={() => setPage((p) => p-1)}
                                className = "rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
                            >
                                Previous
                            </button>
                            <span className="text-sm text-muted-foreground">
                                Page {page} of {data.pages}
                            </span>
                            <button
                                disabled={page >= data.pages}
                                onClick={() => setPage((p) => p + 1)}
                                className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
                            >
                                Next
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}