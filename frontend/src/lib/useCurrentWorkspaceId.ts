import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { workspacesApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

/***
Resolves the current user's default workspace ID.
Caches it on the auth store so subsequent calls are instant.

Returns undefined while loading, and 'null' if the user has no workspace.
*/

export function useCurrentWorkspaceId(): string | null | undefined {
    const workspaceId = useAuthStore ((s) => s.workspaceId);
    const isAuthenticated = useAuthStore ((s) => s.isAuthenticated); 
    const setWorkspaceId = useAuthStore((s) => s.setWorkspaceId);

    const { data, isLoading, isError } = useQuery({
        queryKey: ["workspace", "current"],
        queryFn: () => workspacesApi.current(), 
        enabled: isAuthenticated && !workspaceId, 
        select: (res) => res.data?.id as string, 
        retry: 1, 
    });

    useEffect(() => {
        if (data && data !== workspaceId) {
            setWorkspaceId(data);
        }

    }, [data, workspaceId, setWorkspaceId]);

    if (workspaceId) return workspaceId;
    if (isError) return null;
    if (isLoading) return undefined;
    return data ?? undefined;
}