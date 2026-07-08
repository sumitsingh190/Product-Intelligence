import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Download, Loader2, Sparkles } from "lucide-react";
import { reportsApi } from "@/lib/api";
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";
import { formatRelativeTime } from "@/lib/utils";
import type { Document } from "@/types";

/** PRD Center filters reports down to PRDS and gives quick-export actions. */
export function PRDCenterPage() {
    const qc = useQueryClient();
    const workspaceId = useCurrentWorkspaceId();
    const ready = !!workspaceId;

    const { data, isLoading } = useQuery({ 
        queryKey: ["reports", workspaceId], 
        queryFn: () => reportsApi.list(workspaceId!), 
        select: (res) => res.data, 
        enabled: ready, 
    });

    const generate = useMutation({ 
        mutationFn: () => reportsApi.generate(workspaceId!, "prd"), 
        onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }), 
    });

    const prds: Document[] = (data?.items ?? []).filter(
        (d: Document) => d.document_type === "prd"
    );

    const handleExport = async(docId: string, title: string, format: "markdown" | "pdf") => {
        const res = await reportsApi.export(docId, format); 
        const mime = format === "pdf" ? "application/pdf" : "text/markdown";
        const ext = format == "pdf" ? "pdf" : "md";
        const url = URL.createObjectURL(new Blob([res.data], { type: mime }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `${title}.${ext}`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2x1 font-bold">PRD Center</h1>
                    <p className="mt-1 text-sm text-muted foreground">
                        All product requirement documents generated for this workspace.
                    </p>
                </div>
                <button
                    onclick={() => generate.mutate()}
                    disabled = {generate.isPending}
                    className = "flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                    {generate. IsPending ? <Loader2 className="h-4 w-4 animate-spin" />: <Sparkles className="h-4 w-4"/>}
                    Draft new PRD
                </button>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : prds.length === 0? (
                <div className="rounded-xl border border-dashed border-border p-12 text-center">
                    <FileText className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                    <p className="font-medium">No PRDs yet</p>
                    <p className "mt-1 text-sm text-muted-foreground">
                        Accept a recommendation on the Roadmap and generate a PRD from it.
                    </p>
                </div>
            ) : (
                <div className="space-y-3">
                    {prds.map((doc) => (
                        <div key={doc.id} className="rounded-xl border border-border bg-card p-5">
                            <div className="flex items-start justify-between gap-4">
                                <div className="min-w-0 flex-1">
                                    <h3 className="font-semibold">{doc.title}</h3>
                                    <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                                        {doc.content_preview}
                                    </p>
                                    <p className="mt-2 text-xs text-muted-foreground">
                                        v{doc.version} . {doc.word_count} words . {formatRelativeTime(doc.created_at)}
                                    </p>
                                </div>
                                <div className="flex shrink-0 gap-2">
                                    <button
                                        onClick ={() => handleExport(doc.id, doc.title, "markdown")}
                                        className = "flex items center gap 1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
                                    >
                                        <Download classname="h-3 w-3" />
                                        .md
                                    </button>
                                    <button
                                        onclick={() => handleExport(doc.id, doc.title, "pdf")}
                                        className="flex items-center gap-1.5 rounded-lg border border-border px-3.py-1.5 text-xs font-medium hover:bg-accent"
                                    >
                                        <Download className="h-3 w-3" />
                                        .pdf
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}