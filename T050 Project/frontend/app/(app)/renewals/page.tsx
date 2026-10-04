"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  Calendar, Clock, AlertTriangle, RefreshCw, Shield, Search,
  ArrowRight, ChevronRight, DollarSign, Layers, CheckCircle2,
  FileText, ExternalLink, X
} from "lucide-react";
import { formatCurrency, formatDate, riskColor } from "@/lib/utils";
import { useRealtimeContracts } from "@/lib/realtime";

type HorizonFilter = "all" | "actionRequired" | "next30" | "next90" | "next180" | "autoRenew";

export default function RenewalsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [horizonFilter, setHorizonFilter] = useState<HorizonFilter>("all");
  const [renewModalContract, setRenewModalContract] = useState<any>(null);

  // Real-time synchronization
  const { isConnected } = useRealtimeContracts([], {
    onEvent: () => {
      qc.invalidateQueries({ queryKey: ["renewals"] });
      qc.invalidateQueries({ queryKey: ["contracts"] });
    },
  });

  // Query all renewals (365 days horizon)
  const { data: renewals, isLoading } = useQuery({
    queryKey: ["renewals"],
    queryFn: async () => (await api.get("/obligations/renewals", { params: { days: 365 } })).data,
  });

  // Renewal Mutation
  const renewMutation = useMutation({
    mutationFn: async (contractId: string) => (await api.post(`/contracts/${contractId}/renew`)).data,
    onSuccess: (newContract: any) => {
      toast.success(`Renewal draft created: "${newContract.title}"`);
      qc.invalidateQueries({ queryKey: ["renewals"] });
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
      setRenewModalContract(null);
    },
    onError: (e: any) => {
      toast.error(getErrorMessage(e, "Renewal creation failed"));
    },
  });

  // Calculate high-level KPI metrics
  const counts = useMemo(() => {
    const list = renewals ?? [];
    const totalValue = list.reduce((sum: number, r: any) => sum + (Number(r.value_amount) || 0), 0);
    return {
      all: list.length,
      totalValue,
      actionRequired: list.filter((r: any) => r.action_required).length,
      next30: list.filter((r: any) => r.days_until_expiry >= 0 && r.days_until_expiry <= 30).length,
      next90: list.filter((r: any) => r.days_until_expiry > 30 && r.days_until_expiry <= 90).length,
      next180: list.filter((r: any) => r.days_until_expiry > 90 && r.days_until_expiry <= 180).length,
      autoRenew: list.filter((r: any) => r.auto_renew).length,
    };
  }, [renewals]);

  // Filter renewals
  const filteredRenewals = useMemo(() => {
    return (renewals ?? []).filter((r: any) => {
      // 1. Text Search
      if (search) {
        const term = search.toLowerCase();
        const matches =
          (r.title || "").toLowerCase().includes(term) ||
          (r.contract_number || "").toLowerCase().includes(term) ||
          (r.counterparty || "").toLowerCase().includes(term);
        if (!matches) return false;
      }

      // 2. Risk filter
      if (riskFilter !== "all" && r.risk_level !== riskFilter) return false;

      // 3. Type filter
      if (typeFilter !== "all" && r.contract_type !== typeFilter) return false;

      // 4. Horizon tab filter
      if (horizonFilter === "actionRequired") return r.action_required;
      if (horizonFilter === "next30") return r.days_until_expiry >= 0 && r.days_until_expiry <= 30;
      if (horizonFilter === "next90") return r.days_until_expiry > 30 && r.days_until_expiry <= 90;
      if (horizonFilter === "next180") return r.days_until_expiry > 90 && r.days_until_expiry <= 180;
      if (horizonFilter === "autoRenew") return r.auto_renew;

      return true;
    });
  }, [renewals, search, riskFilter, typeFilter, horizonFilter]);

  return (
    <div className="p-8 max-w-screen-2xl mx-auto space-y-6">
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
              <Calendar className="h-7 w-7 text-brand-600" /> Contract Renewals & Expirations
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                isConnected
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`}></span>
              {isConnected ? "Live Realtime" : "Connecting..."}
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-1">
            Proactive deadline management, auto-renewal opt-out notifications, and contract renewals.
          </p>
        </div>
      </div>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-5 bg-white border border-slate-200 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Value at Risk</span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
              <DollarSign className="h-5 w-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            {formatCurrency(counts.totalValue, "USD")}
          </div>
          <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
            <span className="font-semibold text-slate-700">{counts.all}</span> contracts up for renewal
          </p>
        </div>

        <div className="card p-5 bg-white border border-slate-200 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Action Required</span>
            <div className="w-9 h-9 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
              <AlertTriangle className="h-5 w-5 animate-bounce" />
            </div>
          </div>
          <div className="text-2xl font-bold text-rose-600 mt-2">
            {counts.actionRequired} Contracts
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Notice deadline due or urgent (&lt; 30d)
          </p>
        </div>

        <div className="card p-5 bg-white border border-slate-200 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Auto-Renew Exposure</span>
            <div className="w-9 h-9 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
              <RefreshCw className="h-5 w-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-purple-700 mt-2">
            {counts.autoRenew} Contracts
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Will auto-renew unless opt-out served
          </p>
        </div>

        <div className="card p-5 bg-white border border-slate-200 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Negotiation Window</span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
              <Clock className="h-5 w-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-amber-600 mt-2">
            {counts.next90} Contracts
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Expiring in 30–90 days
          </p>
        </div>
      </div>

      {/* Horizon Filter Tabs */}
      <div className="card p-3 bg-white border border-slate-200 flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2">Window:</span>
        <button
          onClick={() => setHorizonFilter("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            horizonFilter === "all"
              ? "bg-brand-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          All Renewals ({counts.all})
        </button>
        <button
          onClick={() => setHorizonFilter("actionRequired")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            horizonFilter === "actionRequired"
              ? "bg-rose-600 text-white shadow-xs"
              : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
          }`}
        >
          Action Required ({counts.actionRequired})
        </button>
        <button
          onClick={() => setHorizonFilter("next30")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            horizonFilter === "next30"
              ? "bg-amber-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Next 30 Days ({counts.next30})
        </button>
        <button
          onClick={() => setHorizonFilter("next90")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            horizonFilter === "next90"
              ? "bg-amber-500 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          30–90 Days ({counts.next90})
        </button>
        <button
          onClick={() => setHorizonFilter("next180")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            horizonFilter === "next180"
              ? "bg-blue-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          90–180 Days ({counts.next180})
        </button>
        <button
          onClick={() => setHorizonFilter("autoRenew")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            horizonFilter === "autoRenew"
              ? "bg-purple-600 text-white shadow-xs"
              : "bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100"
          }`}
        >
          Auto-Renewing ({counts.autoRenew})
        </button>
      </div>

      {/* Filter & Search Controls */}
      <div className="card p-4 flex flex-wrap items-center justify-between gap-4 bg-slate-50/70">
        <div className="flex items-center gap-2 flex-1 min-w-[260px]">
          <Search className="h-4 w-4 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search by contract name, ID, or counterparty..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input w-full bg-white text-sm"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500">Risk:</span>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="input bg-white text-xs py-1.5 h-9"
            >
              <option value="all">All Risks</option>
              <option value="low">Low Risk</option>
              <option value="medium">Medium Risk</option>
              <option value="high">High Risk</option>
              <option value="critical">Critical Risk</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500">Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="input bg-white text-xs py-1.5 h-9"
            >
              <option value="all">All Types</option>
              <option value="vendor">Vendor</option>
              <option value="supplier">Supplier</option>
              <option value="license">License / SaaS</option>
              <option value="msa">MSA</option>
              <option value="partnership">Partnership</option>
              <option value="nda">NDA</option>
            </select>
          </div>
        </div>
      </div>

      {/* Renewals Table & Cards */}
      <div className="card overflow-hidden bg-white border border-slate-200 shadow-xs">
        {isLoading ? (
          <div className="text-center py-16 text-slate-400">Loading renewal schedules...</div>
        ) : filteredRenewals.length === 0 ? (
          <div className="text-center py-16">
            <Calendar className="h-10 w-10 text-slate-300 mx-auto mb-2" />
            <div className="text-base font-semibold text-slate-700">No renewals matching filter</div>
            <p className="text-xs text-slate-400 mt-1">Try broadening your search or window filter.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/80 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Contract & Counterparty</th>
                  <th className="px-4 py-3.5">Category & Value</th>
                  <th className="px-4 py-3.5">Expiration & Days Left</th>
                  <th className="px-4 py-3.5">Notice Deadline</th>
                  <th className="px-4 py-3.5">Auto-Renew Policy</th>
                  <th className="px-4 py-3.5">Risk Score</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRenewals.map((r: any) => {
                  const daysLeft = r.days_until_expiry;
                  const isOverdue = daysLeft < 0;
                  const isActionRequired = r.action_required;

                  return (
                    <tr key={r.contract_id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Contract Title & Number */}
                      <td className="px-5 py-4">
                        <div className="font-semibold text-slate-900 leading-tight">
                          <Link
                            href={`/contracts/${r.contract_id}`}
                            className="hover:text-brand-600 transition-colors"
                          >
                            {r.title}
                          </Link>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="font-mono text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                            {r.contract_number}
                          </span>
                          <span className="text-xs text-slate-500">
                            {r.counterparty || "Internal / Standard"}
                          </span>
                        </div>
                      </td>

                      {/* Category & Value */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="font-bold text-slate-900">
                          {r.value_amount ? formatCurrency(r.value_amount, r.value_currency || "USD") : "—"}
                        </div>
                        <span className="inline-block mt-0.5 text-xs text-slate-500 uppercase font-semibold">
                          {r.contract_type || "Vendor"}
                        </span>
                      </td>

                      {/* Expiration & Days Left */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="text-xs font-semibold text-slate-800">
                          {formatDate(r.expiration_date)}
                        </div>
                        <div className="mt-1">
                          <span
                            className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${
                              isOverdue
                                ? "bg-red-100 text-red-800 border-red-200"
                                : daysLeft <= 30
                                ? "bg-rose-50 text-rose-700 border-rose-200 animate-pulse"
                                : daysLeft <= 90
                                ? "bg-amber-50 text-amber-700 border-amber-200"
                                : "bg-emerald-50 text-emerald-700 border-emerald-200"
                            }`}
                          >
                            <Clock className="h-3 w-3" />
                            {isOverdue ? `Expired (${Math.abs(daysLeft)}d ago)` : `${daysLeft} days left`}
                          </span>
                        </div>
                      </td>

                      {/* Notice Deadline */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="text-xs font-medium text-slate-700">
                          {formatDate(r.notice_deadline)}
                        </div>
                        <div className="mt-1">
                          {isActionRequired ? (
                            <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
                              <AlertTriangle className="h-3 w-3" /> Notice Due Now
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">
                              {r.renewal_notice_days || 60}d notice window
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Auto-Renew Policy */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        {r.auto_renew ? (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-md">
                            <RefreshCw className="h-3 w-3" /> Auto-Renews
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md">
                            Fixed Term (Expires)
                          </span>
                        )}
                      </td>

                      {/* Risk Score */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span className={`badge ${riskColor(r.risk_level)} text-xs`}>
                          Risk: {r.risk_level} ({Math.round(r.risk_score || 0)})
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setRenewModalContract(r)}
                            className="btn btn-primary bg-brand-600 hover:bg-brand-700 text-white text-xs px-3 py-1.5 inline-flex items-center gap-1.5 shadow-xs"
                          >
                            <RefreshCw className="h-3.5 w-3.5" /> Renew
                          </button>
                          <Link
                            href={`/contracts/${r.contract_id}`}
                            className="btn btn-secondary text-xs px-2.5 py-1.5 inline-flex items-center gap-1 text-slate-600 hover:text-slate-900"
                          >
                            <ExternalLink className="h-3.5 w-3.5" /> View
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Renew Confirmation Modal */}
      {renewModalContract && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="card w-full max-w-md p-6 bg-white shadow-2xl rounded-2xl border border-slate-200">
            <div className="flex items-center justify-between mb-4 border-b pb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600">
                  <RefreshCw className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base">Initiate Contract Renewal</h3>
                  <p className="text-xs text-slate-500">Create next renewal cycle draft agreement</p>
                </div>
              </div>
              <button onClick={() => setRenewModalContract(null)} className="text-slate-400 hover:text-slate-700">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-600 mb-6 bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div className="flex justify-between">
                <span className="font-semibold text-slate-700">Contract:</span>
                <span className="text-slate-900 font-bold">{renewModalContract.title}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-semibold text-slate-700">Contract ID:</span>
                <span className="font-mono text-slate-800">{renewModalContract.contract_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-semibold text-slate-700">Counterparty:</span>
                <span className="text-slate-900">{renewModalContract.counterparty || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-semibold text-slate-700">Annual Value:</span>
                <span className="font-bold text-emerald-700">
                  {renewModalContract.value_amount
                    ? formatCurrency(renewModalContract.value_amount, renewModalContract.value_currency)
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="font-semibold text-slate-700">Current Expiration:</span>
                <span className="text-slate-900">{formatDate(renewModalContract.expiration_date)}</span>
              </div>
            </div>

            <p className="text-xs text-slate-500 mb-6 leading-relaxed">
              This will create a new renewal draft in the system with effective date set to the expiration date of this contract, preserving historical version logs and audit trail.
            </p>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setRenewModalContract(null)}
                className="btn btn-secondary text-xs"
                disabled={renewMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => renewMutation.mutate(renewModalContract.contract_id)}
                disabled={renewMutation.isPending}
                className="btn btn-primary bg-brand-600 hover:bg-brand-700 text-white text-xs inline-flex items-center gap-1.5"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${renewMutation.isPending ? "animate-spin" : ""}`} />
                {renewMutation.isPending ? "Creating Renewal..." : "Confirm & Create Renewal"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
