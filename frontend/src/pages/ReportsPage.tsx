import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Download, Loader2, Sparkles } from "lucide-react";
import { reportsApi } from "@/lib/api";
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";
import { formatRelativeTime } from "@/lib/utils";
import type { Document } from "@/types";

const REPORT_TYPES = [
    {value: "executive_report", label: "Executive Report" },
    { value: "prd", label: "Product Requirement Document" },
    {value: "sprint_plan", label: "Sprint Plan" },
    { value: "product_health", label: "Product Health Report" },
]

export function ReportsPage() {
    const qc = useQueryClient();
    const workspaceId = useCurrentworkspaceId();
    const ready = !!workspaceId;
    const [selectedType, setSelectedType] = useState("executive_report"); 
    const [generating, setGenerating] = useState(false);

    const { data, isLoading} = useQuery({ 
        queryKey: ["reports", workspaceId], 
        queryFn: () => reportsApi.list(workspaceId!), 
        select: (res) => res.data, 
        enabled: ready, 
    });

    const generateReport = useMutation({
        mutationFn: () => reportsApi.generate(workspaceId!, selectedType), 
        onMutate: () => setGenerating(true),
        onSettled: () => setGenerating(false),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["reports"] });
        }
    });

    const handleExport = async (
        docId: string,
        title: string,
        format: "markdown" | "pdf" = "markdown", 
    ) => {
        
        const res = await reportsApi.export(docId, format);
        const mime = format === "pdf" ? "application/pdf": "text/markdown";
        const ext = format === "pdf"? "pdf" : "md"; 
        const url = URL.createObjectURL(new Blob ([res.data], { type: mime }));
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
                    <h1 className="text-2x1 font-bold">Reports</h1>
                    <p className="st-1 text-sm text-muted-foreground">
                        AI-generated PRDS, sprint plans, and executive reports.
                    </p>
                </div>
            </div>

            {/* Generate report */}
            <div className="rounded-xl border border-border bg-card p-5">
                <h2 className="mb-4 font-semibold">Generate New Report</h2>
                <div className="flex flex-wrap gap-3">
                    <select
                        value={selectedType}
                        onChange={(e) => setSelectedType(e.target.value)}
                        className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    >
                        {REPORT_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                    </select>
                    <button
                        onclick={() => generateReport.mutate()}
                        disabled={generating}
                        className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                    >
                        {generating? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="h-4 w-4" />
                        )}
                        Generate
                    </button>
                </div>
                {generating && (
                    <p className="mt-3 text-sm text-muted-foreground">
                        Generating report... this may take 38-60 seconds.
                    </p>
                )}
            </div>

            {/* Reports list */}
            {isLoading ? (
                <div className="flex items-center justify-center.py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <div className="space-y-3">
                    { data?.items.length === 0 ? (
                        < div className="rounded-xl border border-dashed border-border p-12 text-center">
                            <FileText className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                            <p className="font-medium">No reports yet</p>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Generate your first Al report above.
                            </p>
                        </div>
                    ) : (
                        data?.items.map((doc: Document) => (
                            <div
                                key={doc.id}
                                className="flex items-center justify-between rounded-xl border border-border bg-card p-4 hover:bg-accent/30 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="flex h-10 w-18 items-center justify-center rounded-lg bg-primary/10">
                                        <FileText className="h-5 w-5 text-primary" />
                                    </div>
                                    <div>
                                        <p className="font-medium">{doc.title}</p>
                                        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                                            <span className="capitalize">{doc.document_type.replace(" ","")}</span>
                                            <span>.</span>
                                            <span>{doc.word_count} words</span>
                                            <span>.</span>
                                            <span> {formatRelativeTime(doc.created_at)}</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        onclick={() => handleExport(doc.id, doc.title, "markdown")}
                                        className="flex items-center gap-1.5 rounded-lg border border-border px-3 ру-1.5 text-xs hover:bg-accent"
                                    >
                                        <Download className="h-3.5 w-3.5" />
                                        Markdown
                                    </button>
                                    <button
                                        onClick={() => handleExport(doc.id, doc.title, "pdf")}
                                        className="flex items-center gap-1.5 rounded-lg border border-border px-3 ру-1.5 text-xs hover:bg-accent"
                                    >
                                        <Download className="h-3.5 w-3.5" />
                                        PDF
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}