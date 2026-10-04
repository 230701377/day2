import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(n?: number | null, currency = "INR") {
  if (n === null || n === undefined) return "—";
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `${currency} ${n.toLocaleString("en-IN")}`;
  }
}

export function formatDate(d?: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" });
}

export function formatDateTime(d?: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

export function relativeTime(d?: string | null) {
  if (!d) return "—";
  const ms = new Date(d).getTime() - Date.now();
  const abs = Math.abs(ms);
  const days = Math.round(abs / (1000 * 60 * 60 * 24));
  if (days < 1) {
    const hours = Math.round(abs / (1000 * 60 * 60));
    return ms < 0 ? `${hours}h ago` : `in ${hours}h`;
  }
  if (days < 30) return ms < 0 ? `${days}d ago` : `in ${days}d`;
  const months = Math.round(days / 30);
  return ms < 0 ? `${months}mo ago` : `in ${months}mo`;
}

export function statusColor(status: string) {
  switch (status) {
    case "active":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    case "approved":
      return "bg-teal-100 text-teal-800 border-teal-200";
    case "pending_approval":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "analysis_complete":
      return "bg-purple-100 text-purple-800 border-purple-200";
    case "in_review":
      return "bg-blue-100 text-blue-800 border-blue-200";
    case "changes_requested":
      return "bg-orange-100 text-orange-800 border-orange-200";
    case "draft":
      return "bg-slate-100 text-slate-700 border-slate-200";
    case "rejected":
      return "bg-rose-100 text-rose-800 border-rose-200";
    case "renewed":
      return "bg-indigo-100 text-indigo-800 border-indigo-200";
    case "archived":
      return "bg-gray-100 text-gray-600 border-gray-200";
    case "expired":
      return "bg-orange-100 text-orange-800 border-orange-200";
    case "terminated":
      return "bg-red-100 text-red-800 border-red-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

export function riskColor(level: string) {
  switch (level) {
    case "critical":
      return "bg-red-600 text-white";
    case "high":
      return "bg-rose-100 text-rose-800 border-rose-200";
    case "medium":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "low":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

export function severityColor(sev: string) {
  switch (sev) {
    case "critical":
      return "bg-red-600 text-white";
    case "high":
      return "bg-rose-500 text-white";
    case "medium":
      return "bg-amber-500 text-white";
    case "low":
      return "bg-emerald-500 text-white";
    default:
      return "bg-slate-500 text-white";
  }
}

export function roleLabel(role: string) {
  switch (role) {
    case "requester":
      return "Requester";
    case "legal":
      return "Legal";
    case "finance":
      return "Finance";
    case "manager":
      return "Manager";
    case "compliance":
      return "Compliance";
    case "executive":
      return "Executive";
    case "admin":
      return "Administrator";
    default:
      return role;
  }
}
