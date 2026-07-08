import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        port: 5173,
        host: "0.0.0.0",
        proxy: {
            "/api": {
                target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
    build: {
        outDir: "dist",
        sourcemap: true,
        rollupoptions: {
            output: {
                manualChunks: {
                    vendor: ["react", "react-dom", "react-router-dom"],
                    query: ["@tanstack/react-query"],
                    charts: ["echarts", "echarts-for-react"],
                    ui: ["lucide-react", "clsx", "tailwind-merge"],
                },
            },
        },
    },
    test: {
        environment: "happy-dom",
        globals: false,
        include: ["src/**/*.(test, spec}.{ts, tsx}"],
    },
});