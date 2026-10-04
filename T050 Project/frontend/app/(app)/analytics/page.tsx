"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line, Legend,
} from "recharts";
import { formatCurrency } from "@/lib/utils";

const RISK_COLORS = { low: "#10b981", medium: "#f59e0b", high: "#f43f5e", critical: "#dc2626" };

export default function AnalyticsPage() {
  const overview = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: async () => (await api.get("/analytics/overview")).data,
  });
  const riskDist = useQuery({
    queryKey: ["risk-dist"],
    queryFn: async () => (await api.get("/analytics/risk-distribution")).data,
  });
  const byType = useQuery({
    queryKey: ["by-type"],
    queryFn: async () => (await api.get("/analytics/by-type")).data,
  });
  const bottlenecks = useQuery({
    queryKey: ["bottlenecks"],
    queryFn: async () => (await api.get("/analytics/bottlenecks")).data,
  });
  const timeline = useQuery({
    queryKey: ["timeline"],
    queryFn: async () => (await api.get("/analytics/approval-timeline", { params: { days: 30 } })).data,
  });
  const riskTrend = useQuery({
    queryKey: ["risk-trend"],
    queryFn: async () => (await api.get("/analytics/risk-trend", { params: { days: 30 } })).data,
  });
  const obSummary = useQuery({
    queryKey: ["obligations-summary"],
    queryFn: async () => (await api.get("/analytics/obligations-summary")).data,
  });

  return (
    <div className="p-8 max-w-screen-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Analytics</h1>
        <p className="text-slate-500 text-sm mt-1">Risk, contracts, approvals, obligations and renewals.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Total contracts" value={overview.data?.total_contracts ?? 0} />
        <KpiCard label="Active" value={overview.data?.active_contracts ?? 0} />
        <KpiCard label="Pending approvals" value={overview.data?.pending_approvals ?? 0}
                  accent={overview.data?.overdue_approvals ? "rose" : undefined} />
        <KpiCard label="High risk" value={overview.data?.high_risk_count ?? 0} accent="rose" />
        <KpiCard label="Obligations (30d)" value={overview.data?.obligations_due_30d ?? 0} />
        <KpiCard label="Renewals (60d)" value={overview.data?.renewals_due_60d ?? 0} accent="amber" />
        <KpiCard label="Total value" value={formatCurrency(overview.data?.total_value)} />
        <KpiCard label="Overdue approvals" value={overview.data?.overdue_approvals ?? 0} accent="rose" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card p-5">
          <div className="font-semibold mb-3">Risk distribution</div>
          <div className="h-64">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={riskDist.data ?? []} dataKey="count" nameKey="level"
                     innerRadius={50} outerRadius={80}>
                  {(riskDist.data ?? []).map((d: any) => (
                    <Cell key={d.level} fill={(RISK_COLORS as any)[d.level] ?? "#94a3b8"} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card p-5">
          <div className="font-semibold mb-3">Contracts by type</div>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={byType.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="contract_type" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3568ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card p-5">
          <div className="font-semibold mb-3">Approval timeline (30 days)</div>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={timeline.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="submitted" stroke="#3568ff" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="approved" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="rejected" stroke="#f43f5e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card p-5">
          <div className="font-semibold mb-3">Risk findings trend</div>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={riskTrend.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="critical" stroke="#dc2626" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="high" stroke="#f43f5e" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="medium" stroke="#f59e0b" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="low" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card p-5">
        <div className="font-semibold mb-3">Approval bottlenecks (avg hours by step)</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-600 text-xs uppercase">
              <tr>
                <th className="text-left py-2">Step</th>
                <th className="text-right py-2">Avg hours</th>
                <th className="text-right py-2">Pending</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(bottlenecks.data ?? []).map((b: any) => (
                <tr key={b.step_name}>
                  <td className="py-2">{b.step_name}</td>
                  <td className="py-2 text-right">{b.average_hours}</td>
                  <td className="py-2 text-right">{b.pending_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value, accent }: { label: string; value: any; accent?: "rose" | "amber" }) {
  return (
    <div className={`card p-4 ${accent === "rose" ? "border-rose-200" : accent === "amber" ? "border-amber-200" : ""}`}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${accent === "rose" ? "text-rose-600" : accent === "amber" ? "text-amber-600" : "text-slate-900"}`}>
        {value}
      </div>
    </div>
  );
}
