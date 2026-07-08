import { Bell, LogOut, User } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/lib/api";
import { useNavigate } from "react-router-dom";

export function Header() {
    const { user, logout } = useAuthStore();
    const navigate = useNavigate();

    const handleLogout = async () => { 
        try {
            await authApi.logout();
        } finally {
            logout();
            navigate("/login");
        }
    };

    return (
        <header className= "flex h-16 items-center justify-between border-b border-border bg-card px-6">
            <div />
            <div className="flex items-center gap-3">
                <button className="relative rounded-lg p-2 text-muted-foreground hover:bg-accent hover:text-foreground">
                    <Bell className ="h-4 w-4" />
                </button>
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                        <User className="h-4 w-4" />
                    </div>
                    <div className="hidden md:block">
                        <p className="text-sm font-medium leading-none">{user?.full_name}</p>
                        <p className="text-xs text-muted-foreground">{user?.email}</p>
                    </div>
                </div>
                <button>
                    onClick={handleLogout}
                    className="rounded-lg p-2 text-muted-foreground hover:bg-accent hover: text-foreground"
                    title="Logout"
                >
                    <LogOut className="h-4 w-4" />
                </button>
            </div>
        </header>
    );
}
