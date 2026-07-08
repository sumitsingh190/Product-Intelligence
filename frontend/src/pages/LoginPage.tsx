import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, Loader2 } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

type Mode = "login" | "register";

export function LoginPage() {
    const navigate = useNavigate();
    const { setAuth } = useAuthStore();
    const [mode, setMode] = useState<Mode>("login");
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            if (mode === "register") {
                await authApi.register({email, full_name: fullName, password });
            }
        
            const tokenRes = await authApi.login({ email, password });
            const { access_token, refresh_token } = tokenRes.data;
            const meRes = await authApi.me();
            setAuth(meRes.data, access_token, refresh_token);
            navigate("/dashboard");
        } catch (err) {
            const detail =
                (err as { response?: { data?: {detail?: string }}}).response?.data?.detail;
            setError(
                detail ??
                    (mode === "register"
                        ? "Registration failed. Try a different email."
                        : "Invalid email or password.")
            );
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/5 to-background p-4">
            <div className "w-full max-w-md">
        {/* Logo */}
                <div className="mb-8 flex flex-col items-center gap-3">
                    <div className "flex h-14 w-14 items-center justify-center rounded-2xl bg-primary shadow-lg">
                        <Zap className="h-7 w-7 text-white" />
                    </div>
                    <div className="text-center">
                        <h1 className="text-2xl font-bold tracking-tight">ProductOS AI</h1>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Autonomous Product Operating System
                        </p>
                    </div>
                </div>

                <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
                    <div className="mb-6 flex gap-2 rounded-lg bg-muted p-1 text-sm">
                        <button
                            type="button"
                            onClick={() => { setMode("login"); setError(""); }}
                            className = {`flex-1 rounded-md py-1.5 font-medium ${
                                mode === "login"? "bg-background shadow-sm": "text-muted-foreground"
                            }`}
                        >
                            Sign in
                        </button>
                        <button
                            type="button"
                            onclick={() => { setMode("register"); setError(""); }} 
                            className={`flex-1 rounded-md py-1.5 font-medium ${
                                mode "register"? "bg-background shadow-sm": "text-muted-foreground"
                            }`}
                        >
                            Register
                        </button>
                    </div>

                    <h2 className="mb-6 text-xl font-semibold">
                        {mode === "login"? "Sign in to your account": "Create your account"}
                    </h2>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        {mode === "register" && (
                            <div>
                                <label className="mb-1.5 block text-sm font-medium" htmlFor="full name">
                                    Full Name
                                </label>
                                <input>
                                    id = "full_name"
                                    required
                                    value = {fullName}
                                    onChange = {(e) => setFullName(e.target.value)}
                                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="Jane Doe"
                                />
                            </div>
                        )}
                        <div>
                            <label className="mb-1.5 block text-sm font-medium" htmlFor="email">
                                Email
                            </label>
                            <input
                                id="email"
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                                placeholder="you@example.com"
                            />
                        </div>
                        <div>
                            <label className "mb-1.5 block text-se font-medium" htmlFor="password">
                                Password
                            </label>
                            <input  
                                id="password"
                                type="password"
                                required
                                minLength={8}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                                placeholder="At least 8 characters"
                            />
                        </div>

                        {error && (
                            <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                        >

                            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                            {mode === "login"? "Sign in": "Create account"}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}