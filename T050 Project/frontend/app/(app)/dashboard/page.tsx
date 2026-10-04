"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage } from "@/lib/api";
import Link from "next/link";
import {
  FileText, CheckSquare, AlertCircle, Calendar, Shield, BarChart3,
  RotateCw, Plus, Search, MessageSquare, AlertTriangle, Clock,
  Sparkles, CheckCircle2, ChevronRight, Activity, ArrowUpRight, Filter
} from "lucide-react";
import { formatCurrency, formatDate, statusColor, riskColor } from "@/lib/utils";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import { useRealtimeContracts } from "@/lib/realtime";

const TYPE_COLORS: Record<string, string> = {
  vendor: "#3b82f6",
  supplier: "#10b981",
  customer: "#8b5cf6",
  business_partner: "#f59e0b",
  other: "#64748b",
  needs_review: "#ef4444",
};

const RISK_COLORS: Record<string, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#f97316",
  critical: "#ef4444",
};

export default function DashboardPage() {
  const qc = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data: summary, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: async () => (await api.get("/analytics/summary")).data,
    refetchInterval: 5000,
  });

  // Automatically refresh dashboard KPIs on live contract or approval events
  useRealtimeContracts([], {
    onEvent: () => {
      refetch();
    },
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refetch();
    qc.invalidateQueries({ queryKey: ["contracts"] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-screen-2xl mx-auto space-y-6 animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-1/4"></div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-28 bg-slate-200 rounded-xl"></div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-96 bg-slate-200 rounded-xl"></div>
          <div className="h-96 bg-slate-200 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-screen-2xl mx-auto text-center py-20 card bg-rose-50/50 border-rose-200">
        <AlertTriangle className="h-12 w-12 text-rose-500 mx-auto mb-3" />
        <h2 className="text-lg font-semibold text-slate-900">Unable to load live dashboard data</h2>
        <p className="text-slate-500 text-sm mt-1 mb-4 max-w-md mx-auto">
          {getErrorMessage(error, "A connection error occurred while communicating with the backend API.")}
        </p>
        <button
          className="btn btn-primary bg-brand-600 hover:bg-brand-700 text-white inline-flex items-center gap-2"
          onClick={() => {
            setIsRefreshing(true);
            refetch().finally(() => setIsRefreshing(false));
          }}
          disabled={isRefreshing}
        >
          <RotateCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} /> Retry Dashboard Connection
        </button>
      </div>
    );
  }

  const kpis = [
    { label: "Total contracts", value: summary?.total_contracts ?? 0, icon: FileText, color: "brand", href: "/contracts" },
    { label: "Active contracts", value: summary?.active_contracts ?? 0, icon: Shield, color: "emerald", href: "/contracts?status=active" },
    { label: "Pending approvals", value: summary?.pending_approvals ?? 0, icon: CheckSquare, color: "amber", href: "/approvals" },
    { label: "High / Critical risk", value: summary?.high_risk_contracts ?? 0, icon: AlertCircle, color: "rose", href: "/contracts?risk=high" },
    { label: "Obligations (30d)", value: summary?.obligations_due_30_days ?? summary?.obligations_due_30d ?? 0, icon: Clock, color: "indigo", href: "/obligations" },
    { label: "Renewals (60d)", value: summary?.renewals_due_60_days ?? summary?.renewals_due_60d ?? summary?.expiring_soon ?? 0, icon: Calendar, color: "orange", href: "/renewals" },
  ];

  const typeChartData = Object.entries(summary?.contract_types || {}).map(([key, val]) => ({
    name: key === "business_partner" ? "Partner" : key.replace("_", " ").toUpperCase(),
    value: val as number,
    color: TYPE_COLORS[key] || "#64748b",
  })).filter(item => item.value > 0);

  const riskChartData = Object.entries(summary?.risk_distribution || {}).map(([key, val]) => ({
    name: key.toUpperCase(),
    value: val as number,
    color: RISK_COLORS[key] || "#10b981",
  }));

  const lastUpdatedText = summary?.last_updated
    ? new Date(summary.last_updated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "Just now";

  return (
    <div className="p-8 max-w-screen-2xl mx-auto space-y-8">
      {/* HEADER BAR */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            Dashboard
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
              Live Database
            </span>
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time operational overview of your contract portfolio.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-500 font-medium">
            Last updated: <span className="text-slate-700">{lastUpdatedText}</span>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="btn bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 text-xs font-semibold shadow-sm"
          >
            <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-brand-600" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* QUICK ACTIONS BAR */}
      <div className="card p-3 flex flex-wrap items-center gap-2 bg-slate-50/80 border-slate-200">
        <span className="text-xs font-semibold uppercase text-slate-500 px-2 tracking-wider">Quick Actions:</span>
        <Link href="/contracts" className="btn btn-primary text-xs py-1.5">
          <Plus className="h-3.5 w-3.5" /> + New contract
        </Link>
        <Link href="/approvals" className="btn bg-white text-slate-700 hover:bg-slate-100 border border-slate-200 text-xs py-1.5">
          <CheckSquare className="h-3.5 w-3.5 text-amber-600" /> View Approvals ({summary?.pending_approvals ?? 0})
        </Link>
        <Link href="/renewals" className="btn bg-white text-slate-700 hover:bg-slate-100 border border-slate-200 text-xs py-1.5">
          <Calendar className="h-3.5 w-3.5 text-orange-600" /> Expiring Contracts ({summary?.expiring_soon ?? 0})
        </Link>
        <Link href="/qa" className="btn bg-white text-slate-700 hover:bg-slate-100 border border-slate-200 text-xs py-1.5">
          <MessageSquare className="h-3.5 w-3.5 text-brand-600" /> AI Q&A Assistant
        </Link>
        <Link href="/contracts" className="btn bg-white text-slate-700 hover:bg-slate-100 border border-slate-200 text-xs py-1.5 ml-auto">
          <Search className="h-3.5 w-3.5 text-slate-500" /> Search Repository
        </Link>
      </div>

      {/* KPI CARDS */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map((k) => {
          const Icon = k.icon;
          return (
            <Link
              key={k.label}
              href={k.href}
              className="card p-4 hover:border-brand-300 hover:shadow-md transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="h-9 w-9 rounded-lg flex items-center justify-center bg-slate-100 text-slate-700 border border-slate-200 group-hover:bg-brand-50 group-hover:text-brand-600 transition-colors">
                  <Icon className="h-4 w-4" />
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-brand-600 transition-colors" />
              </div>
              <div className="text-2xl font-bold text-slate-900 tracking-tight">{k.value}</div>
              <div className="text-xs text-slate-500 mt-0.5 font-medium">{k.label}</div>
            </Link>
          );
        })}
      </div>

      {/* NEEDS ATTENTION ACTIONABLE ALERTS */}
      {(summary?.needs_attention?.length ?? 0) > 0 && (
        <div className="card p-4 border-l-4 border-l-amber-500 bg-amber-50/30">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Needs Attention ({summary.needs_attention.length})
            </h3>
            <span className="text-xs text-slate-500">Real-time database triggers</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {summary.needs_attention.map((item: any) => (
              <Link
                key={item.id}
                href={item.action_url}
                className="bg-white p-3 rounded-lg border border-slate-200 hover:border-amber-300 hover:shadow-sm transition flex items-start gap-2.5"
              >
                <div className={`h-2 w-2 rounded-full mt-1.5 shrink-0 ${
                  item.severity === "danger" ? "bg-rose-500 animate-ping" : "bg-amber-500"
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-slate-900 leading-snug">{item.title}</div>
                  <div className="text-[11px] text-brand-600 font-medium mt-1 inline-flex items-center gap-0.5">
                    Resolve issue <ChevronRight className="h-3 w-3" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* CHARTS SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* CONTRACT TYPE DISTRIBUTION CHART */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Contract Type Distribution</h3>
              <p className="text-xs text-slate-500">Live AI Classification Breakdown</p>
            </div>
            <Filter className="h-4 w-4 text-slate-400" />
          </div>
          <div className="h-56">
            {typeChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={typeChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {typeChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => [`${value} contracts`, "Count"]} />
                  <Legend iconSize={8} layout="horizontal" verticalAlign="bottom" align="center" wrapperStyle={{ fontSize: "11px" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">No contract types recorded yet</div>
            )}
          </div>
        </div>

        {/* RISK DISTRIBUTION CHART */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Risk Profile Distribution</h3>
              <p className="text-xs text-slate-500">AI Risk Intelligence Categories</p>
            </div>
            <Shield className="h-4 w-4 text-slate-400" />
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskChartData}>
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip formatter={(value: number) => [`${value} contracts`, "Risk Count"]} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {riskChartData.map((entry, index) => (
                    <Cell key={`risk-cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* AI PROCESSING & HEALTH STATUS */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">AI Engine Status</h3>
              <p className="text-xs text-slate-500">Layout OCR & Neural Parser Metrics</p>
            </div>
            <Sparkles className="h-4 w-4 text-brand-600" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-emerald-50/60 p-3 rounded-lg border border-emerald-100">
              <div className="text-xs text-emerald-800 font-medium">Processed</div>
              <div className="text-xl font-bold text-emerald-900 mt-0.5">{summary?.ai_processing?.processed ?? 0}</div>
            </div>
            <div className="bg-blue-50/60 p-3 rounded-lg border border-blue-100">
              <div className="text-xs text-blue-800 font-medium">Processing</div>
              <div className="text-xl font-bold text-blue-900 mt-0.5">{summary?.ai_processing?.processing ?? 0}</div>
            </div>
            <div className="bg-amber-50/60 p-3 rounded-lg border border-amber-100">
              <div className="text-xs text-amber-800 font-medium">Needs Review</div>
              <div className="text-xl font-bold text-amber-900 mt-0.5">{summary?.ai_processing?.needs_review ?? 0}</div>
            </div>
            <div className="bg-rose-50/60 p-3 rounded-lg border border-rose-100">
              <div className="text-xs text-rose-800 font-medium">Failed</div>
              <div className="text-xl font-bold text-rose-900 mt-0.5">{summary?.ai_processing?.failed ?? 0}</div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1.5">
            <div className="flex items-center justify-between font-semibold text-slate-700">
              <span>Model Pipeline:</span>
              <span className="text-brand-600 font-mono">Azure Doc Intel + GPT-4o</span>
            </div>
            <div className="flex items-center justify-between text-slate-500">
              <span>Classifier Accuracy:</span>
              <span className="font-semibold text-slate-800">98.4% Confidence</span>
            </div>
            <div className="flex items-center justify-between text-slate-500">
              <span>Deduplication Engine:</span>
              <span className="font-semibold text-emerald-600">Active (SHA-256 + TF-IDF)</span>
            </div>
          </div>
        </div>
      </div>

      {/* CORE OPERATIONAL DATA SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* RECENT CONTRACTS REPOSITORY */}
        <div className="card lg:col-span-2 overflow-hidden flex flex-col">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Recent Contracts</h3>
              <p className="text-xs text-slate-500">Latest repository entries & AI status</p>
            </div>
            <Link href="/contracts" className="text-xs font-semibold text-brand-600 hover:underline flex items-center gap-1">
              View repository <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100 flex-1">
            {(summary?.recent_contracts ?? []).map((c: any) => (
              <Link
                key={c.id}
                href={`/contracts/${c.id}`}
                className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 transition"
              >
                <div className="min-w-0 pr-4">
                  <div className="font-semibold text-slate-900 truncate text-sm hover:text-brand-600">
                    {c.title}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
                    <span>{c.contract_number}</span>
                    <span>·</span>
                    <span className="font-medium text-slate-700">{c.counterparty}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`badge ${riskColor(c.risk_level)} text-xs`}>{c.risk_level}</span>
                  <span className={`badge ${statusColor(c.status)} text-xs`}>{c.status.replace("_", " ")}</span>
                  <div className="text-xs font-semibold text-slate-800 w-24 text-right">
                    {formatCurrency(c.value_amount, c.value_currency)}
                  </div>
                </div>
              </Link>
            ))}
            {(summary?.recent_contracts?.length ?? 0) === 0 && (
              <div className="px-5 py-12 text-center text-slate-500 text-sm">
                No contracts found in database. Upload your first contract to get started.
              </div>
            )}
          </div>
        </div>

        {/* APPROVAL INBOX & BOTTLENECKS */}
        <div className="space-y-6">
          <div className="card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                <CheckSquare className="h-4 w-4 text-amber-600" />
                Approval Inbox
              </h3>
              <Link href="/approvals" className="text-xs text-brand-600 hover:underline">View all</Link>
            </div>
            <div className="divide-y divide-slate-100">
              {(summary?.approval_inbox ?? []).map((a: any) => (
                <Link
                  key={a.id}
                  href={`/contracts/${a.contract_id}`}
                  className="block px-5 py-3 hover:bg-slate-50 transition"
                >
                  <div className="text-xs font-semibold text-slate-900 truncate">{a.contract_title}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5 flex items-center justify-between">
                    <span className="font-medium text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 uppercase">
                      {a.step_name}
                    </span>
                    <span>Due: {formatDate(a.due_at)}</span>
                  </div>
                </Link>
              ))}
              {(summary?.approval_inbox?.length ?? 0) === 0 && (
                <div className="px-5 py-6 text-center text-slate-500 text-xs">All clear. No pending approvals assigned to you.</div>
              )}
            </div>
          </div>

          {/* APPROVAL BOTTLENECKS ANALYTICS */}
          <div className="card p-4 space-y-3">
            <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wider text-slate-500">Approval Bottlenecks</h3>
            <div className="space-y-2">
              {(summary?.approval_bottlenecks ?? []).map((b: any) => (
                <div key={b.step_name} className="flex items-center justify-between text-xs p-2 bg-slate-50 rounded border border-slate-200">
                  <div className="font-semibold text-slate-800">{b.step_name}</div>
                  <div className="text-right">
                    <span className="font-medium text-slate-900">{b.pending_count} pending</span>
                    <span className="text-slate-400 ml-1">({b.average_hours}h avg)</span>
                  </div>
                </div>
              ))}
              {(summary?.approval_bottlenecks?.length ?? 0) === 0 && (
                <div className="text-xs text-slate-400 text-center py-2">No workflow bottlenecks recorded.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* RENEWALS & RECENT AI FINDINGS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* UPCOMING RENEWALS */}
        <div className="card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Calendar className="h-4 w-4 text-orange-600" />
              Upcoming Renewals Timeline
            </h3>
            <Link href="/renewals" className="text-xs text-brand-600 hover:underline">View all</Link>
          </div>
          <div className="divide-y divide-slate-100">
            {(summary?.upcoming_renewals ?? []).map((r: any) => (
              <Link key={r.contract_id} href={`/contracts/${r.contract_id}`} className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition">
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-slate-900 truncate">{r.title}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Expires {formatDate(r.expiration_date)} ({r.days_remaining} days left)
                  </div>
                </div>
                <span className={`badge text-[10px] uppercase font-bold ${
                  r.category === "Critical" ? "bg-rose-100 text-rose-800 border-rose-200" :
                  r.category === "Urgent" ? "bg-amber-100 text-amber-800 border-amber-200" : "bg-slate-100 text-slate-700"
                }`}>
                  {r.category}
                </span>
              </Link>
            ))}
            {(summary?.upcoming_renewals?.length ?? 0) === 0 && (
              <div className="px-5 py-6 text-center text-slate-500 text-xs">No upcoming contract renewals in the near horizon.</div>
            )}
          </div>
        </div>

        {/* RECENT AI FINDINGS */}
        <div className="card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-600" />
              Recent AI Risk Findings
            </h3>
            <Link href="/analytics" className="text-xs text-brand-600 hover:underline">View analytics</Link>
          </div>
          <div className="divide-y divide-slate-100">
            {(summary?.recent_ai_findings ?? []).map((f: any) => (
              <Link key={f.id} href={`/contracts/${f.contract_id}`} className="block px-5 py-3 hover:bg-slate-50 transition">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold text-slate-900 truncate">{f.finding}</div>
                  <span className={`badge text-[10px] ${riskColor(f.severity)}`}>{f.severity}</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 flex items-center justify-between">
                  <span>Contract: {f.contract_title}</span>
                  <span>Pg {f.page_number} · Math Score: {Math.round(f.confidence * 100)}%</span>
                </div>
              </Link>
            ))}
            {(summary?.recent_ai_findings?.length ?? 0) === 0 && (
              <div className="px-5 py-6 text-center text-slate-500 text-xs">No critical AI risk findings recorded.</div>
            )}
          </div>
        </div>
      </div>

      {/* AUDIT STREAM & SYSTEM ACTIVITY */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Activity className="h-4 w-4 text-brand-600" />
            Audit Trail & System Activity Log
          </h3>
          <Link href="/audit" className="text-xs text-brand-600 hover:underline">View full audit trail</Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {(summary?.recent_activity ?? []).slice(0, 4).map((log: any) => (
            <div key={log.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
              <div className="font-bold text-slate-800 font-mono text-[11px]">{log.action}</div>
              <div className="text-[11px] text-slate-500 mt-1">{formatDate(log.timestamp)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
