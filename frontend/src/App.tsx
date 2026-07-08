import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InsightsPage } from "./pages/InsightsPage";
import { RoadmapPage } from "./pages/RoadmapPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SearchPage } from "./pages/SearchPage";
import { SettingsPage } from "./pages/SettingsPage";
import { PRDCenterPage } from "./pages/PRDCenterPage";
import { AgentActivityPage } from "./pages/AgentActivityPage";
import { EngineeringHealthPage } from "./pages/EngineeringHealthPage";
import { CompetitorWatchPage } from "./pages/CompetitorWatchPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
    const { isAuthenticated } = useAuthStore();
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }
    return <>{children}</>;
}

function App() {
    return (
        <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
                path="/"
                element={
                    <RequireAuth>
                        <AppLayout/>
                    </RequireAuth>
                }
            >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />}/>
                <Route path="insights" element={<InsightsPage />} />
                <Route path="roadmap" element={<RoadmapPage />} />
                <Route path="prds" element={<PRDCenterPage />} />
                <Route path="reports" element={<ReportsPage />} />
                <Route path="competitors" element={<CompetitorWatchPage />} /> 
                <Route path="engineering" element={<EngineeringHealthPage />} />
                <Route path="activity" element={<AgentActivityPage />} />
                <Route path="search" element={<SearchPage />} />
                <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
}

export default App;