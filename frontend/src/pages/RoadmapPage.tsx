import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Map, Sparkles, Loader2, Clock, Users, FileText } from "lucide-react";
import { recommendationsApi, reportsApi } from "@/lib/api";
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";
import { cn, statusColor, formatRelativeTime } from "@/lib/utils";
import type { Recommendation, RecommendationStatus } from "@/types";

const TYPE_LABELS: Record<string, string> = {
    feature: "Feature",
    bug_fix: "Bug Fix",
    performance: "Performance",
    ux: "UX", 
    security: "Security", 
    tech_debt: "Tech Debt",
    research: "Research", 
};

function ScoreBadge({label, value, max=10 }: { label: string; value: number; max?: number }) {
    const pct = (value / max) * 100;
    const color = pct >= 70 ? "bg-green-500": pct >= 40 ? "bg-yellow-500": "bg-red-500";
    return (
        <div className="flex flex-col gap-0.5">
            <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-medium">{value.toFixed(1)}</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted">
                <div className={cn("h-1.5 rounded-full", color)} style={{width: `${pct}%`}} />
            </div>
        </div>
    );
}


export function RoadmapPage() {
    const qc = useQueryClient();
    const workspaceId = useCurrentWorkspaceId();
    const ready = !!workspaceId;
    const [statusFilter, setStatusFilter] = useState<RecommendationStatus | "">("");
    const [page, setPage] = useState(1);

    const { data, isLoading } = useQuery({
        queryKey: ["recommendations", workspaceId, statusFilter, page],
        queryFn: () =>
            recommendationsApi.list(workspaceId!, {
                status: statusFilter || undefined, 
                page, 
            }), 
        select: (res) => res.data, 
        enabled: ready, 
    });

    const generateRecs = useMutation({ 
        mutationFn: () => recommendationsApi.generate(workspaceId!), 
        onSuccess: () => qc.invalidateQueries({queryKey: ["recommendations"] }), 
    });

    const updateStatus = useMutation({ 
        mutationFn: ({ id, status, reason } : { id: string; status: string; reason?: string }) => 
            recommendationsApi.decide(id, status, reason), 
        onSuccess: () => qc.invalidateQueries({querykay: ["recommendations"] }), 
    });

    const generatePrd = useMutation({ 
        mutationFn: (recId: string) =>
            reportsApi.generate(workspaceId!, "prd", recId),
        onSuccess: () => qc.invalidateQueries({queryKey: ["reports"] }),
    });

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Roadmap</h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        AI-prioritized product recommendations with ROI scoring.
                    </p>
                </div>
                <button
                    onClick={() => generateRecs.mutate()}
                    disabled={generateRecs.isPending}
                    className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                    {generateRecs.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ):(
                        <Sparkles className="h-4 w-4" />
                    )}
                    Generate Recommendations
                </button>
            </div>

            <div className="flex gap-3">
                <select
                    value = {statusFilter}
                    onChange={(e) => { setStatusFilter(e.target.value as RecommendationStatus | ""); setPage(1); }}
                    className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm"
                >
                    <option value="">All Statuses</option>
                    <option value="new">New</option>
                    <option value="accepted">Accepted</option>
                    <option value="in progress">In Progress</option>
                    <option value="completed">Completed</option>
                    <option value="rejected">Rejected</option>
                    <option value="deferred">Deferred</option>
                </select>
            </div>

            {isLoading ? (
                <div classMame="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : (
                < div className="space-y-4">
                    {data?.items.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-border p-12 text-center"> 
                            <Map className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                            <p className="font-medium">No recommendations yet</p>
                            <p className="mt-1 text-sa text-muted-foreground">
                                Generate recommendations from your insights to build your roadmap.
                            </p>
                        </div>
                    ) : (
                        data?.items.map((rec: Recommendation) => (
                            <div key={rec.id} className="rounded-xl border border-border bg-card p-5">
                                <div className="flex items-start g-4"> 
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                                        #{rec.priority_rank}
                                    </div>
                                    <div className="flex-1 min-w-8">
                                        <div className="flex flex-wrap items-center gap-2"> 
                                            <span className="rounded-full bg-accent px-2 py-0.5 text-xs font-medium"> 
                                                {TYPE_LABELS[rec.recommendation_type] ?? rec.recommendation_type}
                                            </span>
                                            <span className={cn("rounded-full px-2 py-6.5 text-xs font-medium", statusColor(rec.status))}>
                                                {rec.status.replace("_"," ")}   
                                            </span>
                                        </div>

                                        <h3 className="mt-2 font-semibold">{rec.title}</h3>
                                        <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{rec.description}</p>

                                        <div className="mt-3 grid grid-cols-3 gap-4">
                                            <ScoreBadge label="Impact" value={rec.impact_score} />
                                            <ScoreBadge label="Effort" value={rec.effort_score} />
                                            <ScoreBadge label="ROI" value={rec.roi_score} />
                                        </div>

                                        <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                                            {rec.estimated_effort_days && (
                                                <span className="flex items-center gap-1">
                                                    <Clock className="h-3 w-3" />
                                                    {rec.estimated_effort_days} days
                                                </span>
                                            )}
                                            {rec.estimated_users_impacted && (
                                                <span className="flex items-center gap-1">
                                                    <Users className="h-3 w-3" />
                                                    {rec.estimated_users_impacted.toLocaleString()} users
                                                </span>
                                            )}
                                            <span>{formatRelativeTime(rec.created_at)}</span>
                                        </div>
                                    </div>

                                    {/* Actions */}
                                    {rec.status === "new" && (
                                        <div className="flex shrink-0 flex-col gap-2">
                                            <button
                                                onClick={() => {
                                                    const reason = window.prompt("Reason for accepting? (optional)") || undefined;
                                                    updateStatus.mutate({ id: rec.id, status: "accepted", reason });
                                                }}
                                                className="rounded-lg bg-green-600 px-3.py-1.5 text-xs font-medium text-white hover:bg-green-700"
                                            >
                                                Accept
                                            </button>
                                            <button
                                                onClick={() => {
                                                    const reason = window.prompt("Why reject this recommendation?") || undefined;
                                                    updateStatus.mutate({ id: rec.id, status: "rejected", reason });
                                                }}
                                                className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
                                            >
                                                Reject
                                            </button>
                                        </div>
                                    )}
                                    {(rec.status === "accepted" || rec.status === "in_progress") && (
                                        <div className="flex shrink-0 flex-col gap-2">
                                            <button
                                                onClick={() => generatePrd.mutate(rec.id)}
                                                disabled={generatePrd.isPending}
                                                className="flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/10 disabled:opacity-50"
                                                title="Generate a full PRD for this recommendation"
                                            >
                                                {generatePrd.isPending && generatePrd.variables === rec.id ? (
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                ):(
                                                    <FileText className="h-3 w-3" />
                                                )}
                                                Generate PRD
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))
                    )}


                    {data && data.pages > 1 && (
                        <div className="flex items-center justify-center gap-2 pt-2">
                            <button disabled={page === 1} onClick={() => setPage((p) => p-1)} className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50">
                                Previous
                            </button>
                            <span className="text-sm text-muted-foreground">Page {page} of {data.pages}</span>
                            <button disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)} className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50">
                                Next
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}