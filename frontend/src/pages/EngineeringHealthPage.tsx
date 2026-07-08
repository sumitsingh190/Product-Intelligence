import { useQuery } from "@tanstack/react-query";
import { Wrench, Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { analyticsApi, insightsApi } from "@/lib/api"; 
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";
import { formatRelativeTime, cn, severityColor } from "@/lib/utils";
import type { Insight, KPI } from "@/types";

/** Engineering Health bug rate, sprint velocity, and engineering insights. */

export function EngineeringHealthPage() {
    const workspaceId = useCurrentWorkspaceId();
    const ready = !!workspaceId;

    const kpisQuery = useQuery( {
        queryKey: ["kpis", workspaceId], 
        queryFn: () => analyticsApi.kpis(workspaceId!), 
        select: (res) => res.data as Record<string, KPI>, 
        enabled: ready, });

    const insightsQuery = useQuery({
        queryKey: ["insights", workspaceId, "engineering"], 
        queryFn: () => insightsApi.list(workspaceId!, {insight_type: "engineering"}),
        select: (res) => res.data, 
        enabled: ready, });


    const engineeringkpis: string[] = ["bugs_reported", "sprint_velocity", "ticket_resolution_rate"];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Engineering Health</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                    Bug rate, velocity, and shipping quality insights.
                </p>
            </div>

        /* KPI band */)

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {engineeringkpis.map((name) => {
                    const k = kpisQuery.data?.[name];
                    if (!k) return null;
                    const Icon = k.trend === "up"? TrendingUp : k.trend === "down"? TrendingDown: Minus;
                    return (
                        <div key={name} className="rounded-xl border border-border bg card p-4">
                            <div className="flex items-center justify-between">
                                <p className="text-sm text-muted-foreground">{name.replace(/_/g," ")}</p>
                                <Icon className="h-4 w-4 text-muted-foreground" />
                            </div>
                            <p className "mt-2 text-2xl font-semibold">
                                {k.current_value}
                                <span className="ml-1 text-sm font-normal text muted-foreground">{k.unit}</span> 
                            </p>
                            {k.change_percent !== null && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                    {k.change_percent > 0 ? "+" : ""}
                                    {k.change_percent.toFixed(1)}% vs previous period
                                </p>
                            )}
                        </div>
                    );
                })}
            </div>

            <div>
                <h2 className="mb-3 text-1g font-semibold">Engineering insights</h2>
                {insightsQuery.isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className "h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ): !insightsQuery.data?.items?.length? (
                    <div className "rounded-x1 border border-dashed border-border p-12 text-center"> 
                        <Wrench className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                        <p className="font-medium">No engineering insights yet</p>
                        <p className "mt-1 text-sm text-muted-foreground">
                            Connect GitHub or Jira, then trigger an analysis.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {insightsQuery.data.items.map((i: Insight) => (
                            <div key={i.id} className="rounded-xl border border-border bg-card p-5">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", severityColor(i.severity))}>
                                                {i.severity}
                                            </span>
                                            <span className="text-xs text-muted foreground">
                                                {formatRelativeTime(i.created_at)}
                                            </span>
                                        </div>
                                        <h3 className="mt-2 font-semibold">{i.title}</h3>
                                        <p className="mt-1 text-sm text-muted-foreground">{i.summary}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}