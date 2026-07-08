import { NavLink } from "react-router-dom";
import {
    LayoutDashboard,
    Lightbulb,
    Map,
    FileText,
    Search,
    Settings,
    Zap,
    Activity,
    Swords,
    Wrench,
    FileCode,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
    { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { path: "/insights", label: "Insights", icon: Lightbulb },
    { path: "roadmap", label: "Roadmap", icon: Map },
    { path: "/prds", label: "PRD Center", icon: FileCode },
    { path: "/reports", label: "Reports", icon: FileText },
    { path: "/competitors", label: "Competitor Watch", icon: Swords },
    { path: "/engineering", label: "Engineering Health", icon: Wrench },
    { path: "/activity", label: "Agent Activity", icon: Activity },
    { path: "/search", label: "Search", icon: Search },
    { path: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
    return (
        <aside className="flex w-64 flex-col border-r border-border bg-card">
            <div className="flex h-16 items-center gap-2 border-b border-border px-6">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                    <Zap className="h-4 w-4 text-primary-foreground"/>
                </div>
                <span className="text-lg font-semibold tracking-tight">ProductOS AI</span>
            </div>

            <nav className="flex-1 px-3 py-4">
                <div className="space-y-1">
                    {navItems.map(({ path, label, icon: Icon }) => (
                        <NavLink
                            key={path}
                            to={path}
                            className={({ isActive }) => 
                                cn(
                                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                                    isActive
                                        ? "bg-primary/10 text-primary"
                                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                                )
                            }
                        >
                            <Icon className="h-4 w-4 shrink-0" />
                            {label}
                        </NavLink>
                    ) )}
                </div>
            </nav>
            

            <div className="border-t border-border p-4">
                <p className="text-xs text-muted-foreground">ProductOS AI v0.1.0</p>
            </div>
        </aside>
    );
}