import { create } from "zustand";
import { persist } from "zustand/middleware";

interface User {
    id: string;
    email: string;
    full_name: string;
    workspace_id: string | null;
    role: string;
    is_active: boolean;
}

interface AuthState {
    user: User | null;
    accessToken: string | null;
    refreshToken: string | null;
    isAuthenticated: boolean;
    workspaceId: string | null;
    setAuth: (user: User, accessToken: string, refreshToken: string) => void;
    setUser: (user: User) => void;
    setWorkspaceId: (id: string | null) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            workspaceId: null,

            setAuth: (user, accessToken, refreshToken) =>
                set({ user, accessToken, refreshToken, isAuthenticated: true }),
        
            setUser: (user) => set({user}),

            setWorkspaceId: (id) => set({ workspaceId: id }),

            logout: () =>
                set({
                    user: null,
                    accessToken: null,
                    refreshToken: null,
                    isAuthenticated: false,
                    workspaceId: null,
                }),
        }),
        {
            name: "productos-auth",
            partialize: (state) => ({
                user: state.user,
                accessToken: state.accessToken,
                refreshToken: state.refreshToken,
                isAuthenticated: state.isAuthenticated,
                workspaceId: state.workspaceId,
            }),
        }
    )
);