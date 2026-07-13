import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search as SearchIcon, FileText, Lightbulb, Loader2 } from "lucide-react";
import { searchApi } from "@/lib/api";
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";
import { cn } from "@/lib/utils";

interface SearchHit {
    id : string;
    title : string;
    content_preview?: string;
    document_type?: string;
    kind: "document" | "insight";
    similarity?: number;
    keyword_score?: number;
}

export function SearchPage(){
    const workspaceId = useCurrentWorkspaceId();
    const [input, setInput] = useState("");
    const [query, setQuery] = useState("");
    
    const {data: hits, isFetching, error } = useQuery({
        queryKey : ["search", workspaceId, query],
        queryFn: () => searchApi.query(workspaceId!, query,15),
        select: (res) => res.data as SearchHit[],
        enabled: !!workspaceId && query.length >=2,
        staleTime: 30_000,
    })

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Semantic Search</h1>
                <p className="mt-1 text-muted-foreground">
                    Search insights and documents using natural language.
                </p>
            </div>

            <form 
                onSubmit={(e) => {
                    e.preventDefault();
                    setQuery(input.trim());
                }}
                className="flex items-center gap-2"
            >
                <div className="relative flex-1">
                    <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder='Try "users complaining about login speed" or "tech debt in auth service"'
                        className="w-full rounded-lg border border-border bg-card py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                </div>
                <button
                    type="submit"
                    disabled={input.trim().length < 2}
                    className = "rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                    {isFetching? <Loader2 className="h-4 w-4 animate-spin" />: "Search"}
                </button>
            </form>

            {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                    Search failed. Check that GOOGLE API KEY is configured on the backend.
                </div>
            )}

            {hits && hits.length === 0 && query && (
                <div className="rounded-lg border border-dashed border-border bg-card/50, p-8 text-center text-sm text-muted-foreground">
                    No matches for <strong>{query}</strong>.
                </div>
            )}

            <div className="space-y-3">
                {hits?.map((hit) => (
                    <ResultRow key={`${hit.kind}-${hit.id}`} hit={hit} />
                ))}
            </div>
        </div>
    );
}

function ResultRow({hit}: {hit: SearchHit }) {
    const Icon = hit.kind === "insight" ? Lightbulb: FileText;
    const score = hit.similarity ?? hit.keyword_score ?? 0;

    return (
        <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-4">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <Icon className="h-4 w-4 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <p className="text-sm font medium leading-snug">{hit.title}</p>
                    <span className="rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                        {hit.document_type ?? hit.kind}
                    </span>
                </div>

                {hit.content_preview && (
                    <p className="mt-1 text-xs text-muted foreground line-clamp-2">{hit.content_preview}</p>
                )}
            </div>
            <span
                className={cn(
                    "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
                    score > 0.6 ? "bg-emerald-50 text-emerald-700" : "bg-muted text-muted-foreground"
                )}
                title={hit.similarity !== undefined ? "Vector similarity": "Keyword score"}
            >
                {(score * 100).toFixed(0)}%
            </span>
        </div>
    );
}