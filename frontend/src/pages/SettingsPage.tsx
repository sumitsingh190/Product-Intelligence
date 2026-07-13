import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plug, RefreshCw, Trash2, CheckCircle2, AlertCircle, Plus } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useCurrentWorkspaceId } from "@/lib/useCurrentWorkspaceId";
import { dataSourcesApi } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

type SourceType =
    | "github"
    | "jira"
    | "slack";

type Field = { key: string; label: string; type?: string; placeholder?: string; required?: boolean };

const SOURCE_FIELDS: Record<SourceType, Field[]> = {
    github: [
        { key: "token", label: "Personal Access Token", type: "password", required: true },
        { key: "repos", label: "Repos (comma-separated, e.g. owner/repo)", placeholder: "owner/repo,owner/other", required: true },
    ],
    
    jira: [
        {key: "base_url", label: "Base URL", placeholder: "https://your-org.atlassian.net", required: true },
        {key: "email", label: "Email", required: true },
        {key: "api_token", label: "API Token", type: "password", required: true },
        {key: "project_keys", label: "Project Keys (comma-separated)", placeholder: "PROJ,ENG", required: true },
    ],
    
    slack: [
        {key: "bot_token", label: "Bot Token (xoxb-)", type: "password", required: true },
        {key: "channel_ids", label: "Channel IDs (comma-separated)", placeholder: "C012ABCD, C034EFGH", required: true },
        {key: "history_days", label: "History Days", placeholder: "7"},
    ],
};

const SOURCE_LABELS: Record<SourceType, { name: string; icon: string }> = {
    github: { name: "GitHub", icon: "*"},
    jira: {name: "Jira", icon: "*"},
    slack: { name: "Slack", icon: "*"},
};


interface DataSource {
    id: string;
    name: string;
    source_type: SourceType;
    status: "active" | "inactive" | "error" | "syncing";
    config: Record<string, unknown>;
    last_synced_at: string | null;
    total_records_synced: number;
    last_error: string | null;

function statusBadge(status: DataSource["status"]) {
    const map: Record<DataSource["status"], string> = {
        active: "bg-green-500/10 text-green-700 dark:text-green-400",
        inactive: "bg-muted text-muted foreground",
        error: "bg-destructive/10 text-destructive",
        syncing: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
    };
    
    return (
        <span className={`rounded-md px-2 py-0.5 text-xs font-medium capitalize ${map[status]}`}>
            {status}
        </span>
    );
}

function AddSourceForm({
    workspaceId,
    onDone,
}: {
    workspaceId: string;
    onDone: () => void;
}) {
    const qc = useQueryClient();
    const [sourceType, setSourceType] = useState<SourceType>("github");
    const [name, setName] = useState("");
    const [values, setValues] = useState<Record<string, string>>({});
    const [error, setError] = useState("");

    const create useMutation({
        mutationFn: () => {
            const config: Record<string, unknown> = {};
            for (const f of SOURCE_FIELDS[sourceType]) {
                const v = values[f.key] ?? "";
                if (f.key === "repos" || f.key === "project_keys" || f.key === "channel_ids") {
                    config[f.key] = v.split(",").map((s) => s.trim()).filter(Boolean);
                } else if (f.key === "history_days") {
                    config[f.key] = v? Number(v): 7;
                } else {
                    config[f.key] = v;
                }
            }

            return dataSourcesApi.create(workspaceId, {
                name: name || SOURCE_LABELS[sourceType].name,
                source_type: sourceType,
                config,
            });
        };

        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["dataSources"] });
            onDone();
        },
        
        onError: (e) => {
            const detail = (e as { response?: {data?: {detail?: string} } }).response?.data?.detail;
            setError(detail ?? "Failed to create data source.");
        },
    });

    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                setError("");
                create.mutate();
            }}
            className="space-y-3 rounded-lg border border-border bg-muted/30 p-4"
        >
            <div className="grid gap-3 sm:grid-cols-2">
                <div>
                    <label className="mb-1 block text-xs font-medium text-muted foreground">Type</label>
                    <select
                        value = {sourceType}
                        onChange={(e) => {
                            setSourceType(e.target.value as SourceType);
                            setvalues({});
                        }}
                        className = "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    >
                        {Object.entries(SOURCE_LABELS).map(([k, v]) => (
                            <option key={k} value={k}>
                                {v.icon} {v.name}
                            </option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground"> Name (optional) </label>
                    <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder={SOURCE_LABELS[sourceType].name}
                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    />
                </div>
            </div>

            {SOURCE_FIELDS[sourceType].map((f) => (
                <div key={f.key}>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                        {f.label}
                        {f.required && <span className="text-destructive"> *</span>}
                    </label>
                    <input
                        type={f.type ?? "text"}
                        required={f.required}
                        placeholder={f.placeholder}
                        value={values[f.key] ?? ""}
                        onChange={(e) => setValues((s) => ({ ...s, [f.key]: e.target.value }))}
                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    />
                </div>
            ))}

            {error && (
                <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                    {error}
                </div>
            )}

            <div className="flex gap-2">
                <button
                    type="submit"
                    disabled={create.isPending}
                    className="flex items-center gap-2 rounded-ig bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                    {create.isPending && <Loader2 className "h-3.5 w-3.5 animate-spin" />}
                    Add Source
                </button>
                <button
                    type="button"
                    onClick={onDone}
                    className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"
                >
                    Cancel
                </button>
            </div>
        </form>
    );
}

function CsvUploadForm({ workspaceId }: { workspaceId: string }) {
    const qc = useQueryClient();
    const [kind, setKind] = useState<"reviews" | "support_tickets" | "product_events">("reviews");
    const [name, setName] = useState("");
    const [file, setFile] = useState<File | null>(null); 
    const [error, setError] = useState("");
    const [ok, setOk] = useState(false);

    const upload = useMutation({
        mutationFn: () => {
            if (!file) throw new Error("Pick a CSV file first");
            return dataSourcesApi.uploadCsv (workspaceId, name || file.name, kind, file);
        }, 
        onSuccess: () => {
            qc.invalidateQueries({queryKey: ["dataSources"] }); 
            setFile(null);
            setName("");
            setOk(true);
            setTimeout(() => setOk(false), 3000);
        },
        
        onError: (e) => {
            const detail = (e as { response?: {data?: {detail?: string}}}).response?.data?.detail;
            setError(detail ?? (e as Error).message ?? "Upload failed");
        },
    });

    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                setError("");
                setOk(false);
                upload.mutate();
            }}
            className="space-y-3 rounded-lg border border-border bg-muted/30 p-4"
        >
            <div className="grid gap-3 sm:grid-cols-3">
                <div>
                    <label className "mb-1 block text-xs font-medium text-muted-foreground">Kind</label>.
                    <select
                        value={kind}
                        onChange={(e) => setkind(e.target.value as typeof kind)}
                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    >
                        <option value="reviews">Reviews</option>
                        <option value="support_tickets">Support tickets</option>
                        <option value="product_events">Product events</option>
                    </select>
                </div>
                <div>
                    <label className="mb-1 block text-xs font-medium text-muted foreground">Name (optional)</label>
                    <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Feb 2026 NPS export"
                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    />
                </div>
                <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">CSV file</label>
                    <input
                        type="file"
                        accept=".csv,text/csv"
                        required
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                        className="w-full rounded-lg border border-input bg-background px-3 py-1.5 text-sm"
                    />
                </div>
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}
            {ok && <p className="text-xs text-green-600">CSV uploaded and synced.</p>}
            <div className="flex justify-end">
                <button
                    type="submit"
                    disabled={upload.isPending || !file}
                    className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                    {upload.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                    Upload &amp; sync
                </button>
            </div>
        </form>
    );
}


function SourceRow({source}: {source: DataSource}) {
    const qc = useQueryClient();
    const label = SOURCE_LABELS[source.source_type] ?? {name: source.source_type, icon:"**"};

    const refresh = () => qc.invalidateQueries({queryKey: ["dataSources"]});

    const test = useMutation({
        mutationFn: () => dataSourcesApi.test(source.id),
        onSettled: refresh,
    })

    const sync = useMutation({
        mutationFn: () => dataSourcesApi.sync(source.id),
        onSettled: refresh, 
    });

    const del = useMutation({
        mutationFn: () => dataSourcesApi.delete(source.id), 
        onSettled: refresh, 
    });

    return (
        <div className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <span className="text-xl">{label.icon}</span>
                    <div>
                        <div className="flex items-center gар-2">
                            <span className="text-sm font-medium">{source.name}</span>
                            {statusBadge(source.status)}
                        </div>
                        < div className="mt-0.5 text-xs text-muted-foreground">
                            {source.total_records_synced} records
                            {source.last_synced_at &&
                                ` . last sync ${formatRelativeTime(source.last_synced_at)}`}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => test.mutate()}
                        disabled={test.isPending}
                        title="Test connection"
                        className="flex items-center gap-1 rounded-18 border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-60"
                    >
                        {test.isPending? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ):(
                            <CheckCircle2 className="h-3.5 w-3.5" />
                        )}
                        Test
                    </button>
                    <button
                        onclick={() => sync.mutate()}
                        disabled={sync.isPending}
                        title="Sync now"
                        className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-60"
                    >
                        {sync.isPending? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ):(
                            <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        Sync
                    </button>
                    <button
                        onClick ={() => {
                            if (confirm(`Delete data source "${source.name}"?`)) del.mutate();
                        }}
                        disabled={del.isPending}
                        title="Delete"
                        className="flex items-center rounded-lg border border-border px-2 py-1.5 text-xs font medium text-destructive hover:bg-destructive/10 disabled:opacity-60"
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>
            {source.last_error && (
                <div className="mt-2 flex items-start gap-2 rounded-md bg-destructive/10 p-2 text-xs text-destructive">
                    <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span className="break-words">{source.last_error}</span>
                </div>
            )}
        </div>
    );
}

export function SettingsPage() {
    const { user } = useAuthStore();
    const  workspaceId  = useCurrentWorkspaceId();
    const ready = !!workspaceId;
    const [showAdd, setShowAdd] = useState(false);

    const { data, isLoading } = useQuery({
        queryKey: ["dataSources", workspaceId],
        queryFn: () => dataSourcesApi.list(workspaceId!),
        select: (res) => (res.data?.items ?? res.data) as DataSource[],
        enabled: ready,
    });

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Settings</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                    Manage your account, workspace, and data source connections.
                </p>
            </div>

            {/* Profile */}

            <section className="rounded-xl border border-border bg-card p-6">
                <h2 className="mb-4 font-semibold">Profile</h2>
                <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground">Full Name</label>
                        <p className="mt-1 text-sm">{user?.full_name}</p>
                    </div>
                    <div>
                        <label className "block text-sm font-medium text-muted-foreground">Email</label>
                        <p className="mt-1 text-sm">{user?.email}</p>
                    </div>
                    <div>
                        <label className "block text-sm font-medium text muted-foreground">Role</label>
                        <p className="mt-1 text-sm capitalize">{user?.role}</p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground">Account Status</label>
                        <p className="mt-1 text-sm">{user.is_active ? "Active": "Inactive"}</p>
                    </div>
                </div>
            </section>

            <section className="rounded-xl border border-border bg-card p-6">
                <div className="mb-4 flex items-center justify-between">
                    <div>
                        <h2 className="font-semibold">Data Source Connections</h2>
                        <p className "text-sm text-muted-foreground">
                            Connect external tools to feed signals into ProductOS AI.
                        </p>
                    </div>

                    {ready && !showAdd && (
                        <button
                            onClick={() => setShowAdd(true)}
                            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                        >
                            <Plus className="h-4 w-4" /> Add Source
                        </button>
                    )}
                </div>

                {!ready && (
                    <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                        <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                        Resolving workspace...
                    </div>
                )}

                {ready && showAdd && (
                    <div className="mb-4">
                        <AddSourceForm workspaceId={workspaceId!} onDone={()=>setShowAdd(false)} />
                    </div>
                )}

                {ready && isLoading && (
                    <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading sources...
                    </div>
                )}

                {ready && !isLoading && (data?.length ?? 0) && !showAdd &&(
                    <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                        <Plug className="mx-auto mb-2 h-5 w-5" />
                            No data sources yet. Click <strong>Add Source</strong> to connect one.
                    </div>
                )}

                {ready && !isLoading && (data?.length ?? 0) > 0 && (
                    <div className="space-y-2">
                        {data!.map((s) => (
                            <SourceRow key={s.id} source={s} />
                        ))}
                    </div>
                )}
            </section>

            {ready && (
                <section className = "rounded-xl border border-border bg-card p-6">
                    <h2 className="font-semibold">Upload CSV</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Bulk-import reviews, support tickets, or product events from a
                        spreadsheet. Rows land directly in DuckDB analytics tables.
                    </p>
                    <CsvUploadForm workspaceId={workspaceId!} />
                </section>
            )}

            <section className="rounded-xl border border-border bg-card p-6">
                <h2 className="mb-2 font-semibold">AI Configuration</h2>
                <p className="mb-4 text-sm text-muted-foreground">
                    Configure the Al model used for analysis and generation.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground">LLM Provider</label>
                        <p className="mt-1 text-sm">Groq</p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground">Model</label>
                        <p className="mt-1 text-sm font-mono text-xs">llama-3.3-70b-versatile</p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-muted foreground">Embeddings</label>
                        <p className="mt-1 text-sm">Google AI Studio</p>
                    </div>
                    <div>
                        <label className "block text sm font-medium text-muted-foreground">Embedding Model</label>
                        <p className="mt-1 text-sm font-mono text-xs">text-embedding-004 (768 dims)</p>
                    </div>
                </div>
                <p className="mt-4 text-xs text-muted-foreground">
                    Configure via <code className="font-mono text-xs">GROQ API_KEY</code>,{" "}
                    <code className="font-mono text-xs">GROQ MODEL</code>, and{" "}
                    <code className="font-mono text-xs">GOOGLE API KEY</code> in your{" "}
                    <code className="font-mono text-xs">.env</code> file.
                </p>
            </section>
        </div>
    );
}