import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";

export function cn(...inputs: ClassValue[]) { 
    return twMerge(clsx(inputs)); 
}

export function formatRelativeTime (date: string | Date): string { 
    return formatDistanceToNow (new Date(date), { addSuffix: true });
}

export function formatDate(date: string | Date, fmt = "MMM d, yyyy"): string {
    return format(new Date(date), fmt);
}

export function formatScore(score: number, decimals = 1): string { 
    return score.toFixed(decimals);
}

export function severityColor (severity: string): string {
    const map: Record<string, string> = { 
        critical: "text-red-600 bg-red-50", 
        high: "text-orange-600 bg-orange-50", 
        medium: "text-yellow-600 bg-yellow-50", 
        low: "text-blue-600 bg-blue-50", 
        info: "text-gray-600 bg-gray-50",
    };
    return map[severity] ?? "text-gray-600 bg-gray-50";
}

export function statusColor(status: string): string {
    const map: Record<string, string> = {
        new: "text-blue-700 bg-blue-50",
        acknowledged: "text-yellow-700 bg-yellow-50",
        in_progress: "text-purple-700 bg-purple-50",
        resolved: "text-green-700 bg-green-50",
        dismissed: "text-gray-500 bg-gray-50",
        accepted: "text-green-700' bg-green-50",
        rejected: "text-red-700 bg-red-50",
        completed: "text-green-700 bg-green-50",
        deferred: "text-gray-600 bg-gray-50",
    };
    return map[status] ?? "text-gray-600 bg-gray-50";
}

export function truncate (text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
        return text.slice(0, maxLength) + "...";
}