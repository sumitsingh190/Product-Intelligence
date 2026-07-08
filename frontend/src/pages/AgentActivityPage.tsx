import { useQuery } from "@tanstack/react-query";
import { Activity, Loader2 } from "lucide-react";
import { recommendationsApi} from "@/lib/api";
import { useCurrentWorkspaceId} from "@/lib/useCurrentWorkspaceId";
import { formatRelativeTime, cn} from "@/lib/utils";
import type { AgentDecision } from "@/types";

const DECISION_COLOR: Record<string, string> = {
    accepted: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300", 
    rejected: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300", 
    deferred: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300", 
    in_progress: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300", 
    completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
};
/** Agent Activity chronological log of accept/reject/defer decisions so PMs can see how their calls train the planner's future recommendations. */

export function AgentActivityPage() {
    const workspaceId = useCurrentWorkspaceId();
    const ready = !!workspaceId;

    const { data, isLoading } = useQuery({
        queryKey: ["agent-decisions", workspaceId], 
        queryFn: () => recommendationsApi.decisions(workspaceId!, 200), 
        select: (res) => res.data as AgentDecision[], 
        enabled: ready, });

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Agent Activity</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                    Every accept, reject, and defer decision. The planner reads this log 
                    on future runs so it can avoid repeating rejected ideas. 
                </p>
            </div>

            {isLoading? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ): !data || data.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border p-12 text-center">
                    <Activity className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                    <p className="font-medium">No decisions yet</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Accept or reject a recommendation on the Roadmap to start building
                        the decision log.
                    </p>
                </div>
            ) : (
                <div className="space-y-3">
                    {data.map((d) => {
                        const title = (d.snapshot as { title?: string })?.title ?? d.recommendation_id.slice(0, 8);
                        return (
                            <div key={d.id} className="rounded-xl border border-border bg-card p-5">
                                <div className="flex items-start justify-between gaр-4">
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span
                                                className={cn(
                                                    "rounded-full px-2 py-0.5 text-xs font-medium",
                                                    DECISION COLOR[d.decision] ?? "bg-muted text-muted-foreground"
                                                )}
                                            >
                                                {d.decision.replace("_", " ")}
                                            </span>
                                            <span className="text-xs text-muted-foreground">
                                                {formatRelativeTime(d.created at)}
                                            </span>
                                        </div>
                                        <h3 className="mt-2 font-semibold">{title}</h3>
                                        {d.reason && (
                                            <p className="mt-1 text-sm text-muted-foreground">
                                                <span className="font-medium">Reason:</span> {d.reason}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}