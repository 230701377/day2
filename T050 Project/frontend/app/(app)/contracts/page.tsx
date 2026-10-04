"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  Plus, Search, Filter, Upload, Sparkles, Trash2,
  CheckCircle2, Clock, AlertTriangle, ShieldCheck, Radio,
  RotateCw, ArrowRight, Check, X, AlertCircle
} from "lucide-react";
import { useAuth } from "@/lib/api";
import { formatCurrency, formatDate, statusColor, riskColor } from "@/lib/utils";
import { useRealtimeContracts, ContractItem } from "@/lib/realtime";

export default function ContractsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [showNew, setShowNew] = useState(false);
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data: initialContracts, isLoading, error, refetch } = useQuery({
    queryKey: ["contracts"],
    queryFn: async () => (await api.get("/contracts", {
      params: { limit: 100 }
    })).data,
  });

  // Real-time synchronization hook for Supabase Realtime and WebSockets
  const { contracts, isConnected } = useRealtimeContracts(initialContracts ?? []);

  const { data: templates } = useQuery({
    queryKey: ["templates"],
    queryFn: async () => (await api.get("/templates")).data,
  });

  // Recalculate status counters live from real database records
  const now = new Date();
  const in30Days = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

  const counts = useMemo(() => {
    return {
      total: contracts.length,
      draft: contracts.filter((c) => c.status === "draft").length,
      processing: contracts.filter(
        (c) => c.status === "processing" || c.processing_status === "PROCESSING" || c.processing_status === "QUEUED"
      ).length,
      ready_for_review: contracts.filter(
        (c) => c.status === "analysis_complete" || c.status === "in_review"
      ).length,
      pending_approval: contracts.filter((c) => c.status === "pending_approval").length,
      approved: contracts.filter((c) => c.status === "approved").length,
      active: contracts.filter((c) => c.status === "active").length,
      rejected: contracts.filter((c) => c.status === "rejected").length,
      changes_requested: contracts.filter((c) => c.status === "changes_requested").length,
      high_risk: contracts.filter((c) => c.risk_level === "high" || c.risk_level === "critical").length,
      expiring_soon: contracts.filter((c) => {
        if (!c.expiration_date) return false;
        const d = new Date(c.expiration_date);
        return d >= now && d <= in30Days;
      }).length,
      expired: contracts.filter((c) => {
        if (!c.expiration_date) return false;
        return new Date(c.expiration_date) < now;
      }).length,
    };
  }, [contracts]);

  // Live filter evaluation preserving current search and filters
  const filteredContracts = useMemo(() => {
    return contracts.filter((c) => {
      if (q) {
        const term = q.toLowerCase();
        const match =
          c.title?.toLowerCase().includes(term) ||
          c.contract_number?.toLowerCase().includes(term) ||
          c.counterparty?.toLowerCase().includes(term);
        if (!match) return false;
      }
      if (status) {
        if (status === "pending_approval") return c.status === "pending_approval";
        if (status === "ready_for_review") return c.status === "analysis_complete" || c.status === "in_review";
        if (status === "processing") return c.status === "processing" || c.processing_status === "PROCESSING" || c.processing_status === "QUEUED";
        if (status === "high_risk") return c.risk_level === "high" || c.risk_level === "critical";
        if (status === "expiring_soon") {
          if (!c.expiration_date) return false;
          const d = new Date(c.expiration_date);
          return d >= now && d <= in30Days;
        }
        if (status === "expired") {
          if (!c.expiration_date) return false;
          return new Date(c.expiration_date) < now;
        }
        return c.status === status;
      }
      if (type && c.contract_type !== type) return false;
      return true;
    });
  }, [contracts, q, status, type]);

  const create = useMutation({
    mutationFn: async ({ payload, file }: { payload: any; file?: File }) => {
      toast.loading("Creating contract record...", { id: "create-contract-toast" });
      const c = (await api.post("/contracts", payload)).data;

      if (file) {
        try {
          toast.loading("Uploading document & queuing AI processing...", { id: "create-contract-toast" });
          const formData = new FormData();
          formData.append("file", file);
          formData.append("version_label", "initial");
          formData.append("force_duplicate", "true");
          await api.post(`/contracts/${c.id}/versions`, formData);
        } catch (fileErr: any) {
          try {
            await api.delete(`/contracts/${c.id}`);
          } catch (_) {}
          throw fileErr;
        }
      }
      return c;
    },
    onSuccess: (c) => {
      toast.success("Contract uploaded! AI Processing running in background.", { id: "create-contract-toast" });
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
      setShowNew(false);
      window.location.href = `/contracts/${c.id}`;
    },
    onError: (e: any) => {
      const errMsg = getErrorMessage(e, "Contract creation failed");
      toast.error(errMsg, { id: "create-contract-toast", duration: 8000 });
    },
  });

  const cleanupDuplicates = useMutation({
    mutationFn: async () => (await api.post("/contracts/cleanup-duplicates")).data,
    onSuccess: (data: any) => {
      toast.success(data.message || "Duplicate contracts cleaned up!");
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Cleanup failed")),
  });

  const deleteContract = useMutation({
    mutationFn: async (contractId: string) => (await api.delete(`/contracts/${contractId}`)).data,
    onSuccess: (data: any) => {
      toast.success(data.message || "Contract deleted successfully");
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Delete failed")),
  });

  return (
    <div className="p-8 max-w-screen-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">Contracts</h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                isConnected
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
              title={isConnected ? "Realtime connected via Supabase/WebSocket" : "Connecting to realtime channel..."}
            >
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`}></span>
              {isConnected ? "Live Realtime Active" : "Connecting..."}
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-1">
            Displaying {filteredContracts.length} of {contracts.length} authorized contracts from database.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-300 text-xs font-semibold"
            onClick={() => cleanupDuplicates.mutate()}
            disabled={cleanupDuplicates.isPending}
          >
            <Sparkles className="h-4 w-4 text-brand-600" />
            {cleanupDuplicates.isPending ? "Purging Duplicates..." : "Clean Duplicates"}
          </button>
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>
            <Plus className="h-4 w-4" />
            New contract
          </button>
        </div>
      </div>

      {/* Recalculated Live Status Bar (Requirement 12 & 13) */}
      <div className="card p-3 bg-slate-50 border border-slate-200 overflow-x-auto">
        <div className="flex items-center gap-2 min-w-max text-xs">
          <span className="font-semibold text-slate-600 mr-1">Live Database Metrics:</span>
          <button
            onClick={() => setStatus("")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "" ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
            }`}
          >
            All ({counts.total})
          </button>
          <button
            onClick={() => setStatus(status === "draft" ? "" : "draft")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "draft" ? "bg-slate-700 text-white border-slate-700" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
            }`}
          >
            Draft ({counts.draft})
          </button>
          <button
            onClick={() => setStatus(status === "processing" ? "" : "processing")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "processing" ? "bg-blue-600 text-white border-blue-600" : "bg-white text-blue-700 border-blue-200 hover:bg-blue-50"
            }`}
          >
            Processing ({counts.processing})
          </button>
          <button
            onClick={() => setStatus(status === "ready_for_review" ? "" : "ready_for_review")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "ready_for_review" ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-indigo-700 border-indigo-200 hover:bg-indigo-50"
            }`}
          >
            Ready for Review ({counts.ready_for_review})
          </button>
          <button
            onClick={() => setStatus(status === "pending_approval" ? "" : "pending_approval")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "pending_approval" ? "bg-amber-600 text-white border-amber-600" : "bg-white text-amber-700 border-amber-200 hover:bg-amber-50"
            }`}
          >
            Pending Approval ({counts.pending_approval})
          </button>
          <button
            onClick={() => setStatus(status === "approved" ? "" : "approved")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "approved" ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-emerald-700 border-emerald-200 hover:bg-emerald-50"
            }`}
          >
            Approved ({counts.approved})
          </button>
          <button
            onClick={() => setStatus(status === "active" ? "" : "active")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "active" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-teal-700 border-teal-200 hover:bg-teal-50"
            }`}
          >
            Active ({counts.active})
          </button>
          <button
            onClick={() => setStatus(status === "changes_requested" ? "" : "changes_requested")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "changes_requested" ? "bg-orange-600 text-white border-orange-600" : "bg-white text-orange-700 border-orange-200 hover:bg-orange-50"
            }`}
          >
            Changes Req ({counts.changes_requested})
          </button>
          <button
            onClick={() => setStatus(status === "rejected" ? "" : "rejected")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "rejected" ? "bg-rose-600 text-white border-rose-600" : "bg-white text-rose-700 border-rose-200 hover:bg-rose-50"
            }`}
          >
            Rejected ({counts.rejected})
          </button>
          <button
            onClick={() => setStatus(status === "high_risk" ? "" : "high_risk")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "high_risk" ? "bg-red-700 text-white border-red-700" : "bg-white text-red-700 border-red-200 hover:bg-red-50"
            }`}
          >
            High Risk ({counts.high_risk})
          </button>
          <button
            onClick={() => setStatus(status === "expiring_soon" ? "" : "expiring_soon")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "expiring_soon" ? "bg-amber-700 text-white border-amber-700" : "bg-white text-amber-700 border-amber-200 hover:bg-amber-50"
            }`}
          >
            Expiring Soon ({counts.expiring_soon})
          </button>
          <button
            onClick={() => setStatus(status === "expired" ? "" : "expired")}
            className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
              status === "expired" ? "bg-slate-600 text-white border-slate-600" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-100"
            }`}
          >
            Expired ({counts.expired})
          </button>
        </div>
      </div>

      {/* Filter and Search controls */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[240px] relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Search title, counterparty, number..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="ready_for_review">Ready for review</option>
            <option value="pending_approval">Pending approval</option>
            <option value="approved">Approved</option>
            <option value="active">Active</option>
            <option value="changes_requested">Changes requested</option>
            <option value="rejected">Rejected</option>
            <option value="renewed">Renewed</option>
            <option value="expiring_soon">Expiring soon</option>
            <option value="expired">Expired</option>
            <option value="archived">Archived</option>
          </select>
          <select className="input w-auto" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">All types</option>
            <option value="nda">NDA</option>
            <option value="msa">MSA</option>
            <option value="sow">SOW</option>
            <option value="vendor">Vendor</option>
            <option value="employment">Employment</option>
            <option value="lease">Lease</option>
            <option value="license">License</option>
            <option value="partnership">Partnership</option>
            <option value="service">Service</option>
            <option value="other">Other</option>
          </select>
          {(q || status || type) && (
            <button
              onClick={() => { setQ(""); setStatus(""); setType(""); }}
              className="btn bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Contract Repository Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-500">
            <RotateCw className="h-8 w-8 animate-spin mx-auto text-brand-600 mb-3" />
            Loading contracts from database...
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <AlertTriangle className="h-8 w-8 text-rose-500 mx-auto mb-2" />
            <p className="text-slate-900 font-semibold">Failed to load contracts</p>
            <p className="text-slate-500 text-sm mt-1 mb-4">{getErrorMessage(error, "Connection error")}</p>
            <button className="btn btn-primary" onClick={() => refetch()}>Retry</button>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs uppercase">
              <tr>
                <th className="text-left px-5 py-3 font-semibold">Contract</th>
                <th className="text-left px-5 py-3 font-semibold">Type</th>
                <th className="text-left px-5 py-3 font-semibold">Counterparty</th>
                <th className="text-right px-5 py-3 font-semibold">Value</th>
                <th className="text-left px-5 py-3 font-semibold">Status</th>
                <th className="text-left px-5 py-3 font-semibold">Risk</th>
                <th className="text-left px-5 py-3 font-semibold">Current Step</th>
                <th className="text-left px-5 py-3 font-semibold">Approval Progress</th>
                <th className="text-left px-5 py-3 font-semibold">Expires</th>
                <th className="text-right px-5 py-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredContracts.map((c: ContractItem) => (
                <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                  {/* Title & Number */}
                  <td className="px-5 py-3.5">
                    <Link href={`/contracts/${c.id}`} className="font-medium text-slate-900 hover:text-brand-600">
                      {c.title}
                    </Link>
                    <div className="text-xs text-slate-500 mt-0.5">{c.contract_number}</div>
                  </td>

                  {/* Contract Type */}
                  <td className="px-5 py-3.5">
                    <span className="badge bg-indigo-50 text-indigo-700 border-indigo-200 text-xs font-semibold">
                      {c.contract_type === "vendor" ? "Vendor" :
                       c.contract_type === "supplier" ? "Supplier" :
                       c.contract_type === "customer" || c.contract_type === "license" ? "Customer" :
                       c.contract_type === "partnership" ? "Business Partner" :
                       c.contract_type === "auto_detect" ? "Auto Detect" : (c.contract_type || "Vendor")}
                    </span>
                  </td>

                  {/* Counterparty */}
                  <td className="px-5 py-3.5 text-slate-700">{c.counterparty || "—"}</td>

                  {/* Value */}
                  <td className="px-5 py-3.5 text-right text-slate-700 font-medium">
                    {formatCurrency(c.value_amount, c.value_currency)}
                  </td>

                  {/* Status */}
                  <td className="px-5 py-3.5">
                    {c.processing_status === "PROCESSING" || c.processing_status === "QUEUED" ? (
                      <span className="badge bg-blue-50 text-blue-700 border-blue-200 text-xs font-semibold animate-pulse inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
                        {c.processing_step || "Processing"} ({c.processing_progress || 0}%)
                      </span>
                    ) : c.processing_status === "FAILED" ? (
                      <span className="badge bg-red-50 text-red-700 border-red-200 text-xs font-semibold">
                        Failed
                      </span>
                    ) : (
                      <span className={`badge ${statusColor(c.status || "draft")}`}>{(c.status || "draft").replace("_", " ")}</span>
                    )}
                  </td>

                  {/* Risk */}
                  <td className="px-5 py-3.5">
                    <span className={`badge ${riskColor(c.risk_level || "low")}`}>
                      {c.risk_level || "low"} · {Math.round(c.risk_score || 0)}
                    </span>
                  </td>

                  {/* Current Approval Step (Requirement 9) */}
                  <td className="px-5 py-3.5">
                    <span className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-800 font-semibold border border-slate-200 inline-block">
                      {c.current_approval_step || (
                        c.status === "approved" ? "Approved" :
                        c.status === "active" ? "Active" :
                        c.status === "rejected" ? "Rejected" :
                        c.status === "changes_requested" ? "Changes Requested" :
                        c.status === "draft" ? "Draft" :
                        c.status === "analysis_complete" ? "Ready for Review" :
                        c.status.replace("_", " ")
                      )}
                    </span>
                  </td>

                  {/* Approval Progress Flow: Legal → Manager → Finance → Compliance (Requirement 10) */}
                  <td className="px-5 py-3.5">
                    {c.approval_steps && c.approval_steps.length > 0 ? (
                      <div className="flex items-center flex-wrap gap-1 text-[11px]">
                        {c.approval_steps.map((step, idx) => {
                          const isApproved = step.decision === "approved";
                          const isActive = step.decision === "pending";
                          const isRejected = step.decision === "rejected";
                          const isChanges = step.decision === "changes_requested";
                          const roleName = step.required_role === "legal" ? "Legal" :
                                           step.required_role === "manager" ? "Manager" :
                                           step.required_role === "finance" ? "Finance" :
                                           step.required_role === "compliance" ? "Compliance" :
                                           step.step_name.replace(" Review", "");

                          return (
                            <span key={step.id || idx} className="inline-flex items-center">
                              {idx > 0 && <span className="text-slate-300 mx-0.5">→</span>}
                              <span
                                className={`px-1.5 py-0.5 rounded font-medium ${
                                  isApproved
                                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                    : isActive
                                    ? "bg-blue-50 text-blue-700 border border-blue-300 animate-pulse font-semibold"
                                    : isRejected
                                    ? "bg-rose-50 text-rose-700 border border-rose-200"
                                    : isChanges
                                    ? "bg-amber-50 text-amber-700 border border-amber-200"
                                    : "bg-slate-100 text-slate-500 border border-slate-200"
                                }`}
                                title={`Step ${idx + 1}: ${step.step_name} - ${step.decision.toUpperCase()}`}
                              >
                                {isApproved ? "✓ " : isActive ? "● " : isRejected ? "✕ " : isChanges ? "⚠ " : "○ "}
                                {roleName}
                              </span>
                            </span>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-[11px] text-slate-400">
                        <span>Legal</span>
                        <span>→</span>
                        <span>Manager</span>
                        <span>→</span>
                        <span>Finance</span>
                        <span>→</span>
                        <span>Compliance</span>
                      </div>
                    )}
                  </td>

                  {/* Expires */}
                  <td className="px-5 py-3.5 text-slate-700">{formatDate(c.expiration_date)}</td>

                  {/* Actions */}
                  <td className="px-5 py-3.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Are you sure you want to delete "${c.title}"?`)) {
                          deleteContract.mutate(c.id);
                        }
                      }}
                      className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors inline-flex items-center gap-1"
                      title="Delete Contract"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {filteredContracts.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={10} className="text-center text-slate-500 py-12">
                    No contracts match current search or filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showNew && (
        <NewContractDialog
          templates={templates ?? []}
          onClose={() => setShowNew(false)}
          onCreate={(payload, file) => create.mutate({ payload, file })}
        />
      )}
    </div>
  );
}

function NewContractDialog({
  templates, onClose, onCreate,
}: { templates: any[]; onClose: () => void; onCreate: (payload: any, file?: File) => void }) {
  const [form, setForm] = useState<any>({
    title: "", contract_type: "auto_detect", counterparty: "",
    value_amount: "", value_currency: "USD",
    description: "", template_id: "",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setSelectedFile(file);
    setDuplicateWarning(null);

    const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
    setForm((prev: any) => ({ ...prev, title: prev.title || cleanName }));

    // Instant backend pre-flight duplicate check (works for PDF, DOCX, TXT)
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/ai/detect-duplicates-file", formData);
      if (res.data?.has_duplicate && res.data?.matches?.length > 0) {
        const top = res.data.matches[0];
        setDuplicateWarning(`DUPLICATE CONTRACT DETECTED (${top.similarity_percentage} Match): This document matches existing contract '${top.matched_contract_name}' (${top.matched_contract_number}). Creating this contract will be blocked by system rules.`);
      }
    } catch (err) {
      console.warn("Pre-flight duplicate check error:", err);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async () => {
    if (!form.title.trim()) {
      toast.error("Please enter a contract title");
      return;
    }
    setIsUploading(true);
    try {
      await onCreate({
        ...form,
        value_amount: form.value_amount === "" ? null : Number(form.value_amount),
        template_id: form.template_id || null,
      }, selectedFile || undefined);
    } catch (e) {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
      <div className="card w-full max-w-2xl p-6 bg-white shadow-2xl rounded-2xl border border-slate-200">
        <div className="flex items-center justify-between mb-4 border-b pb-3">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Upload & Create Contract</h2>
            <p className="text-xs text-slate-500 mt-0.5">Upload a PDF/DOCX or fill in contract details for AI processing.</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl font-semibold">×</button>
        </div>

        <div className="space-y-4">
          {/* File Upload Dropzone */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Contract Document (PDF, DOCX, TXT)</label>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer ${
                dragActive ? "border-brand-500 bg-brand-50/50" : selectedFile ? "border-emerald-500 bg-emerald-50/30" : "border-slate-300 hover:border-brand-400 bg-slate-50/50"
              }`}
              onClick={() => {
                const el = document.getElementById("file-input");
                if (el) el.click();
              }}
            >
              <input
                id="file-input"
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]);
                }}
              />
              {selectedFile ? (
                <div className="flex items-center justify-center gap-3">
                  <Upload className="h-6 w-6 text-emerald-600 animate-bounce" />
                  <div className="text-left">
                    <div className="text-sm font-semibold text-slate-900">{selectedFile.name}</div>
                    <div className="text-xs text-emerald-600 font-medium">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready for Azure AI Parsing
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  <Upload className="h-8 w-8 text-slate-400 mx-auto" />
                  <div className="text-sm font-medium text-slate-700">Drag & drop your contract file here, or browse</div>
                  <div className="text-xs text-slate-400">Supports PDF, DOCX, TXT (Max 25MB)</div>
                </div>
              )}
            </div>

            {duplicateWarning && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-start gap-2 animate-in fade-in">
                <span className="font-bold text-red-800 shrink-0">⚠️ DUPLICATE BLOCKED:</span>
                <div>{duplicateWarning}</div>
              </div>
            )}
          </div>

          <div>
            <label className="label">Contract Title *</label>
            <input className="input" placeholder="e.g. Master Services Agreement 2026" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Relationship & Contract Type</label>
              <select className="input" value={form.contract_type}
                      onChange={(e) => setForm({ ...form, contract_type: e.target.value })}>
                <option value="auto_detect">✨ Auto Detect with AI (Default)</option>
                <option value="vendor">Vendor Service Contract</option>
                <option value="supplier">Supplier & Procurement Contract</option>
                <option value="customer">Customer Contract</option>
                <option value="license">Customer & Software Licensing (SaaS)</option>
                <option value="partnership">Business Partner & NDA</option>
                <option value="msa">Master Services Agreement (MSA)</option>
                <option value="employment">Independent Contractor / Employment</option>
                <option value="lease">Commercial Lease (Landlord / Tenant)</option>
                <option value="sow">Statement of Work (SOW)</option>
                <option value="other">Other Commercial Agreement</option>
              </select>
            </div>
            <div>
              <label className="label">Counterparty</label>
              <input className="input" placeholder="e.g. Acme Corp" value={form.counterparty}
                     onChange={(e) => setForm({ ...form, counterparty: e.target.value })} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Contract Value</label>
              <div className="flex gap-2">
                <select className="input w-24" value={form.value_currency} onChange={(e) => setForm({ ...form, value_currency: e.target.value })}>
                  <option value="USD">USD ($)</option>
                  <option value="INR">INR (₹)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                </select>
                <input className="input flex-1" type="number" placeholder="50000" value={form.value_amount}
                       onChange={(e) => setForm({ ...form, value_amount: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="label">Template (optional)</label>
              <select className="input" value={form.template_id}
                      onChange={(e) => setForm({ ...form, template_id: e.target.value })}>
                <option value="">No template</option>
                {templates.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Description / Scope Notes</label>
            <textarea className="input" rows={2} placeholder="Optional notes about contract scope..." value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2 border-t pt-4">
          <button className="btn btn-secondary" onClick={onClose} disabled={isUploading}>Cancel</button>
          <button
            className={`btn min-w-[140px] ${duplicateWarning ? "bg-red-600 hover:bg-red-700 text-white cursor-not-allowed opacity-80" : "btn-primary"}`}
            onClick={handleSubmit}
            disabled={isUploading || Boolean(duplicateWarning)}
          >
            {isUploading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                Processing...
              </span>
            ) : duplicateWarning ? "Duplicate Blocked" : "Create & Analyze AI"}
          </button>
        </div>
      </div>
    </div>
  );
}
