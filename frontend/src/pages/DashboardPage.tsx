import { useQuery } from "@tanstack/react-query"

import ReactECharts from "echarts-for-react";

import {
    Lightbulb,
    Map,
    AlertTriangle,
    BarChart3,
    TrendingUp,
    TrendingDown,
    Minus,
} from "lucide-react";

import { analyticsApi, insightsApi, recommendationsApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useCurrentWorkspaceId} from "@/lib/useCurrentWorkspaceId";
import { cn } from "@/lib/utils";
import type { Insight, KPI, KPIHistoryPoint, Recommendation } from "@/types";

function StatCard({
    title,
    value,
    subtitle,
    icon: Icon,
}: {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: React.ComponentType<{ className?: string }>;

}) {
    return (
        <div className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-sm text-muted-foreground">{title}</p>
                    <p className="mt-1 text-2xl font-bold">{value}</p>
                    { subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
                </div>
                <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10")}>
                    <Icon className="h-5 w-5 text-primary" />
                </div>
            </div>
        </div>
    );
}

function TrendIcon({ trend }: {trend: KPI["trend"] }) {
    const Icon = trend === "up"? TrendingUp: trend === "down"? TrendingDown: Minus;
    const color =
        trend === "up"
            ? "text-emerald-600"
            : trend === "down"
                ? "text-rose-600"
                :"text-muted-foreground";
    return <Icon className={cn("h-4 w-4", color)}/>;
}

function KPICard({ kpi, workspaceId }: { kpi: KPI; workspaceId: string}) {
    const { data : history } = useQuery({
        queryKey: ["kpi-history", workspaceId , kpi.metric_name],
        queryFn: () => analyticsApi.history (workspaceId, kpi.metric_name, 30),
        select: (res) => res.data as KPIHistoryPoint[],
        staleTime: 60_000,
    });

    const option = {
        grid: { top: 4, right: 4, bottom: 4, left: 4 },
        xAxis: { type: "category", show: false, data: (history ?? []).map((p) => p.snapshot_date) },
        yAxis: { type: "value", show: false },
        tooltip: { trigger: "axis", appendToBody: true },
        series: [
            {
                type: "line",
                smooth: true,
                showSymbol: false, 
                lineStyle: { width: 2, color: "#6366f1"}, 
                areastyle: { color: "rgba(99, 102, 241, 0.12)" }, 
                data: (history ?? []).map((p) => p.metric_value), 
            },
        ],
    },

    const prettyName = kpi.metric_name
        .replace(/_/g," ") 
        .replace(/\b\w/g, (c) => c.toUpperCase());

    return (
        <div className="rounded-xl border border-border bg-card p-5">
            <div className "flex items-start justify-between">
                <p className="text-sm text-muted-foreground">{prettyName}</p>
                <TrendIcon trend = {kpi.trend} />
            </div>
            <div className="mt-1 flex items-baseline gap-1">
                <p className="text-2xl font-bold">{ kpi.current_value }</p>
                {kpi.unit && <span className="text-xs text-muted-foreground">{kpi.unit}</span>}
            </div>
            {kpi.change_percent !== null && (
                <p  
                    className={cn(
                        "mt-0.5 text-xs"
                        kpi.change percent > 0 ? "text-emerald-600": "text-rose-600"
                    )}
                >
                    {kpi.change_percent > 0 ? "+": ""}
                    {kpi.change_percent.toFixed(1)} % vs prior period
                </p>
            )}
            {history && history.length > 1 && (
                <div className="mt-3 h-12">
                    <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
                </div>
            )}
        </div>
    );
}

function InsightCard({ insight }: { insight: Insight }) {
    const severityColors: Record<string, string> = {
        critical: "border-l-red-500 bg-red-50/50",
        high: "border-l-orange-500 bg-orange-50/50",
        medium: "border-l-yellow-500 bg-yellow-50/50",
        low: "border-l-blue-500 bg-blue-50/50",
        info: "border-l-gray-400 bg-gray-50/50",
    };

    return (
        <div className={cn("rounded-lg border border-border border-l-4 p-4", severityColors[insight.severity])}>
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium leading-snug">{insight.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{insight.summary}</p>
                </div>
                <span className="shrink-0 rounded-full border border-current/20 px-2 py-0.5 text-xs font-medium capitalize">
                    {insight.severity}
                </span>
            </div>
        </div>
    )
}

function RecommendationCard({ rec }: { rec: Recommendation }) {
    return (
        <div className="flex items-start gap-3 rounded-lg border border-border p-4 hover:bg-accent/50 transition-colors">
            <div className="flex h-8 w-8 shrink-e items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                {rec.priority_rank}
            </div>
            <div className="flex-1 min-w-8">
                <p className="text-sm font-medium leading-snug">{rec.title}</p>
                <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>ROI: <strong className="text-foreground">{rec.roi_score.toFixed(1)}</strong></span> 
                    <span>Impact: <strong className="text-foreground">{rec.impact_score.toFixed(1)}/10</strong></span>
                    <span>Effort: <strong className="text-foreground">{rec.effort_score.toFixed(1)}/10</strong></span>
                </div>
            </div>
        </div>
    );
}

export function DashboardPage() {
    const { user } =  useAuthStore();
    const workspaceId = useCurrentWorkspaceId();
    const ready = !!workspaceId;

    const { data: insights } = useQuery({ 
        queryKey: ["insights", workspaceId, "new"], 
        queryfn: () => insightsApi.list(workspaceId!, {status: "new", page_size: 5}), 
        select: (res) => res.data, enabled: ready, 
    });

    const { data: recommendations } = useQuery({ 
        queryKey: ["recommendations", workspaceId], 
        queryFn: () => recommendationsApi.list (workspaceId!, {page_size: 5}), 
        select: (res) => res.data, enabled: ready, 
    });

    const { data: kpis } = useQuery({ 
        querykey: ["kpis", workspaceId], 
        queryFn: () => analyticsApi.kpis (workspaceId!), 
        select: (res) => res.data as KPI[], 
        enabled: ready, 
        refetchInterval: 60_000, 
    });

    const criticalCount = insights?.items.filter((i: Insight) => i.severity === "critical").length ?? 0; 
    const highCount = insights?.items.filter((i: Insight) => i.severity === "high").length ?? 0;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Welcome back, {user?.full_name?.split(" ")[0]}</h1>
                <p className="mt-1 text-muted-foreground">
                    Here's your product intelligence summary. 
                </p>
            </div>


            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard
                    title="New Insights"
                    value={insights?.total ?? "-"}
                    subtitle="Since last analysis"
                    icon={Lightbulb}
                />
                <StatCard
                    title="Critical Issues"
                    value={criticalCount}
                    subtitle={`${highCount} high severity`}
                    icon={AlertTriangle}
                />
                <StatCard
                    title="Recommendations"
                    value={recommendations?.total ?? "-"}
                    subtitle="Awaiting review"
                    icon={Map}
                />
                <StatCard
                    title="Tracked KPIS"
                    value={kpis?.length ?? "-"}
                    subtitle="From connected sources"
                    icon={BarChart3}
                />
            </div>

    /* Live KPI cards with sparkline trends */

            {kpis && kpis.length > 0 && (
                <div>
                    <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Product Health KPIS
                    </h2>
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {kpis.map((k) => (
                            <KPICard key={k.metric_name} kpi={k} workspaceId={workspaceId!} />
                        ))}
                    </div>
                </div>
            )}

            {kpis && kpis.length === 0 && (
                <div className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center">
                    <p className="text-sm text-muted-foreground">
                        No KPI data yet. Connect a data source on the Settings page and click <strong>Sync</strong> to populate metrics.
                    </p>
                </div>
            )}


            <div className = "grid gap-6 lg:grid-cols-2">

            /* Recent Insights */
                <div className="rounded-xl border border-border bg-card p-5">
                    <div className="mb-4 flex items-center justify-between">
                        <h2 className="font-semibold">Latest Insights</h2>
                        <a href="/insights" className="text-xs text-primary hover:underline">View all</a>
                    </div>
                    <div className="space-y-3">
                        {insights?.items.length === 0 && (
                            <p className="text-sm text-muted-foreground">No insights yet. Trigger an analysis to get started</p>
                        )}
                        {insights?.items.map((insight: Insight) => (
                            <InsightCard key={insight.id} insight={insight} />
                        ))}
                    </div>
                </div>

            /* Top Recommendations */

                <div className="rounded-xl border border-border bg-card p-5">
                    <div className="mb-4 flex items-center justify-between">
                        <h2 className="font-semibold">Top Recommendations</h2>
                        <a href="/roadmap" className="text-xs text-primary hover:underline">View all</a>
                    </div>
                    <div className="space-y-3">
                        {recommendations?.items.length === 0 && (
                            <p className="text-sm text-muted-foreground">No recommendations yet. Generate recommendations from insights. </p>
                        )}
                        {recommendations?.items.map((rec: Recommendation) => (
                            <RecommendationCard key={rec.id} rec={rec} />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}