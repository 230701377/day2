"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  CheckCircle2, Clock, Lock, XCircle, RotateCcw, AlertTriangle,
  Search, Shield, ChevronRight, ExternalLink, Filter, Layers
} from "lucide-react";
import { formatCurrency, formatDateTime, relativeTime, riskColor, statusColor } from "@/lib/utils";
import { useRealtimeContracts } from "@/lib/realtime";

type DecisionType = "approved" | "rejected" | "changes_requested" | null;

export default function ApprovalsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // Modal State
  const [activeApproval, setActiveApproval] = useState<any>(null);
  const [decisionModal, setDecisionModal] = useState<DecisionType>(null);
  const [comments, setComments] = useState("");

  // Real-time synchronization for instant inbox & contracts refresh
  useRealtimeContracts([], {
    onEvent: () => {
      qc.invalidateQueries({ queryKey: ["approvals-inbox"] });
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["contract-approvals-timeline"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
  });

  // 1. Fetch actionable inbox (pending approval items)
  const { data: inboxData, isLoading: isLoadingInbox } = useQuery({
    queryKey: ["approvals-inbox"],
    queryFn: async () => (await api.get("/approvals/inbox")).data,
  });

  // 2. Fetch all contracts from repository
  const { data: allContracts, isLoading: isLoadingContracts } = useQuery({
    queryKey: ["contracts"],
    queryFn: async () => (await api.get("/contracts", { params: { limit: 100 } })).data,
  });

  const decideMutation = useMutation({
    mutationFn: async ({ id, decision, comments }: { id: string; decision: string; comments: string }) =>
      (await api.post(`/approvals/${id}/decide`, { decision, comments })).data,
    onSuccess: (res: any) => {
      toast.success("Decision recorded successfully!");
      qc.invalidateQueries({ queryKey: ["approvals-inbox"] });
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["contract-approvals-timeline"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
      closeModal();
    },
    onError: (e: any) => {
      toast.error(getErrorMessage(e, "Action failed"));
    },
  });

  const closeModal = () => {
    setActiveApproval(null);
    setDecisionModal(null);
    setComments("");
  };

  const handleConfirmDecision = () => {
    if (!activeApproval || !decisionModal) return;
    if ((decisionModal === "rejected" || decisionModal === "changes_requested") && !comments.trim()) {
      toast.error("Please provide a reason or comment.");
      return;
    }
    decideMutation.mutate({
      id: activeApproval.id,
      decision: decisionModal,
      comments: comments.trim(),
    });
  };

  // Group inbox items by contract so each contract appears ONCE in inbox view
  const inboxGrouped = useMemo(() => {
    const raw = inboxData ?? [];
    return Array.from(new Map(raw.map((item: any) => [item.contract_id, item])).values());
  }, [inboxData]);

  // Status counts across active contracts (excluding rejected contracts)
  const activeContracts = useMemo(() => {
    return (allContracts ?? []).filter((c: any) => c.status !== "rejected");
  }, [allContracts]);

  const counts = useMemo(() => {
    const list = activeContracts;
    return {
      all: list.length,
      actionable: inboxGrouped.length,
      pending: list.filter((c: any) => c.status === "pending_approval").length,
      in_review: list.filter((c: any) => c.status === "in_review").length,
      approved: list.filter((c: any) => c.status === "approved").length,
      ready: list.filter((c: any) => c.status === "analysis_complete").length,
      draft: list.filter((c: any) => c.status === "draft").length,
    };
  }, [activeContracts, inboxGrouped]);

  // Filter and prepare full contract approval list
  const displayList = useMemo(() => {
    const contractsList = activeContracts;
    
    // Map each contract to the card item structure
    const mapped = contractsList.map((c: any) => {
      const inboxMatch = (inboxData ?? []).find((ib: any) => ib.contract_id === c.id);
      return {
        id: inboxMatch?.id || `contract-${c.id}`,
        contract_id: c.id,
        contract_title: c.title,
        contract_number: c.contract_number,
        counterparty: c.counterparty,
        contract_type: c.contract_type,
        value_amount: c.value_amount,
        value_currency: c.value_currency,
        risk_level: c.risk_level,
        risk_score: c.risk_score,
        status: c.status,
        step_name: inboxMatch?.step_name || c.current_approval_step || "Review",
        hasPendingAction: Boolean(inboxMatch),
      };
    });

    return mapped.filter((item: any) => {
      // 1. Never show rejected contracts on approval page
      if (item.status === "rejected") return false;

      // 2. Text Search filter
      if (search) {
        const term = search.toLowerCase();
        const matches =
          (item.contract_title || "").toLowerCase().includes(term) ||
          (item.contract_number || "").toLowerCase().includes(term) ||
          (item.counterparty || "").toLowerCase().includes(term);
        if (!matches) return false;
      }

      // 3. Risk filter
      if (riskFilter !== "all" && item.risk_level !== riskFilter) return false;

      // 4. Type filter
      if (typeFilter !== "all" && item.contract_type !== typeFilter) return false;

      // 5. Status tab filter
      if (statusFilter === "actionable") return item.hasPendingAction;
      if (statusFilter === "pending") return item.status === "pending_approval";
      if (statusFilter === "in_review") return item.status === "in_review";
      if (statusFilter === "approved") return item.status === "approved";
      if (statusFilter === "ready") return item.status === "analysis_complete";
      if (statusFilter === "draft") return item.status === "draft";

      return true;
    });
  }, [activeContracts, inboxData, search, riskFilter, typeFilter, statusFilter]);

  const isLoading = isLoadingInbox && isLoadingContracts;

  return (
    <div className="p-8 max-w-screen-2xl mx-auto space-y-6">
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Shield className="h-7 w-7 text-brand-600" /> Approval Management Inbox
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Actionable sequential contract approvals and complete multi-tier workflow status.
          </p>
        </div>
        
        {/* Metric Badges */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 bg-white px-4 py-2 rounded-xl border border-slate-200 shadow-xs">
            <Clock className="h-5 w-5 text-amber-600 animate-pulse" />
            <div>
              <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Actionable Inbox</div>
              <div className="text-lg font-bold text-slate-900 leading-none mt-0.5">
                {counts.actionable} Pending Tasks
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 bg-white px-4 py-2 rounded-xl border border-slate-200 shadow-xs">
            <Layers className="h-5 w-5 text-brand-600" />
            <div>
              <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Total Repository</div>
              <div className="text-lg font-bold text-slate-900 leading-none mt-0.5">
                {counts.all} Contracts
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Status Filter Tab Pills */}
      <div className="card p-3 bg-white border border-slate-200 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1 mr-2">
          View Filter:
        </span>
        <button
          onClick={() => setStatusFilter("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "all"
              ? "bg-brand-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          All Contracts ({counts.all})
        </button>
        <button
          onClick={() => setStatusFilter("actionable")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "actionable"
              ? "bg-amber-500 text-white shadow-xs"
              : "bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100"
          }`}
        >
          Actionable Inbox ({counts.actionable})
        </button>
        <button
          onClick={() => setStatusFilter("pending")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "pending"
              ? "bg-amber-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Pending Approval ({counts.pending})
        </button>
        <button
          onClick={() => setStatusFilter("in_review")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "in_review"
              ? "bg-blue-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          In Review ({counts.in_review})
        </button>
        <button
          onClick={() => setStatusFilter("approved")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "approved"
              ? "bg-emerald-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Approved ({counts.approved})
        </button>
        <button
          onClick={() => setStatusFilter("ready")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "ready"
              ? "bg-purple-600 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Ready for Review ({counts.ready})
        </button>
        <button
          onClick={() => setStatusFilter("draft")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            statusFilter === "draft"
              ? "bg-slate-700 text-white shadow-xs"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Drafts ({counts.draft})
        </button>
      </div>

      {/* Filter & Search Controls */}
      <div className="card p-4 flex flex-wrap items-center justify-between gap-4 bg-slate-50/70">
        <div className="flex items-center gap-2 flex-1 min-w-[260px]">
          <Search className="h-4 w-4 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search by contract name, number, or counterparty..."
            className="input text-xs w-full bg-white"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
            <Filter className="h-3.5 w-3.5" /> Risk Level:
          </div>
          <select
            className="input text-xs w-32 bg-white"
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
          >
            <option value="all">All Risks</option>
            <option value="critical">Critical Risk</option>
            <option value="high">High Risk</option>
            <option value="medium">Medium Risk</option>
            <option value="low">Low Risk</option>
          </select>

          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium ml-2">
            Type:
          </div>
          <select
            className="input text-xs w-36 bg-white"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All Types</option>
            <option value="vendor">Vendor</option>
            <option value="supplier">Supplier</option>
            <option value="license">Customer / SaaS</option>
            <option value="partnership">Business Partner</option>
          </select>
        </div>
      </div>

      {/* Contract Approval Cards List */}
      <div className="space-y-6">
        {displayList.map((item: any) => (
          <ContractApprovalCard
            key={item.id}
            item={item}
            onOpenDecision={(decisionType, activeStep) => {
              setActiveApproval({
                ...item,
                ...(activeStep || {}),
                id: activeStep?.id || item.id,
                step_name: activeStep?.step_name || item.step_name,
              });
              setDecisionModal(decisionType);
            }}
          />
        ))}

        {displayList.length === 0 && !isLoading && (
          <div className="card p-12 text-center bg-white border border-slate-200">
            <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-800">No Contracts Found</h3>
            <p className="text-slate-500 text-sm mt-1">
              No contracts match the currently selected search or status filters.
            </p>
          </div>
        )}
      </div>

      {/* Decision Confirmation Modal */}
      {decisionModal && activeApproval && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                {decisionModal === "approved" && <CheckCircle2 className="h-6 w-6 text-emerald-600" />}
                {decisionModal === "rejected" && <XCircle className="h-6 w-6 text-rose-600" />}
                {decisionModal === "changes_requested" && <RotateCcw className="h-6 w-6 text-amber-600" />}
                <h3 className="text-lg font-bold text-slate-900">
                  {decisionModal === "approved" && "Approve Contract Step"}
                  {decisionModal === "rejected" && "Reject Contract"}
                  {decisionModal === "changes_requested" && "Request Contract Changes"}
                </h3>
              </div>
              <button
                onClick={closeModal}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                ×
              </button>
            </div>

            <div className="space-y-4">
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200/80 text-xs">
                <div className="font-bold text-slate-900 text-sm">
                  {activeApproval.contract_title}
                </div>
                <div className="text-slate-500 mt-1 flex items-center gap-3">
                  <span>No: {activeApproval.contract_number}</span>
                  <span>Step: {activeApproval.step_name}</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  {decisionModal === "approved" ? "Approval Comments (Optional)" : "Reason / Feedback (Required)"}
                </label>
                <textarea
                  rows={4}
                  className="input text-xs w-full p-3 resize-none"
                  placeholder={
                    decisionModal === "approved"
                      ? "Enter optional approval notes or compliance references..."
                      : decisionModal === "rejected"
                      ? "Specify mandatory reason for rejecting this contract..."
                      : "Specify required modifications or clause revisions for the contract owner..."
                  }
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  className="btn btn-secondary text-xs"
                  onClick={closeModal}
                  disabled={decideMutation.isPending}
                >
                  Cancel
                </button>
                <button
                  className={`btn text-xs ${
                    decisionModal === "approved"
                      ? "btn-primary bg-emerald-600 hover:bg-emerald-700 text-white"
                      : decisionModal === "rejected"
                      ? "btn-danger bg-rose-600 hover:bg-rose-700 text-white"
                      : "bg-amber-600 hover:bg-amber-700 text-white"
                  }`}
                  onClick={handleConfirmDecision}
                  disabled={decideMutation.isPending}
                >
                  {decideMutation.isPending
                    ? "Processing..."
                    : decisionModal === "approved"
                    ? "Confirm Approval"
                    : decisionModal === "rejected"
                    ? "Reject Contract"
                    : "Submit Change Request"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ContractApprovalCard({
  item,
  onOpenDecision,
}: {
  item: any;
  onOpenDecision: (decision: DecisionType, activeStep?: any) => void;
}) {
  const { data: contractSteps } = useQuery({
    queryKey: ["contract-approvals-timeline", item.contract_id],
    queryFn: async () => (await api.get(`/approvals/contract/${item.contract_id}`)).data,
  });

  const steps = contractSteps || [item];

  return (
    <div className="card overflow-hidden border border-slate-200 hover:border-slate-300 transition-all shadow-xs bg-white">
      {/* Card Header */}
      <div className="p-6 border-b border-slate-100 bg-gradient-to-r from-slate-50/80 via-white to-slate-50/50">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1 min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <Link
                href={`/contracts/${item.contract_id}`}
                className="text-lg font-bold text-slate-900 hover:text-brand-600 transition flex items-center gap-1.5 group"
              >
                {item.contract_title || "Contract Approval Request"}
                <ExternalLink className="h-4 w-4 text-slate-400 group-hover:text-brand-600" />
              </Link>
              <span className="badge bg-slate-100 text-slate-700 border-slate-200 font-mono text-xs">
                {item.contract_number}
              </span>
              <span className={`badge ${statusColor(item.status || "draft")}`}>
                {(item.status || "draft").replace("_", " ")}
              </span>
              <span className={`badge ${riskColor(item.risk_level)}`}>
                Risk: {item.risk_level?.toUpperCase()} ({Math.round(item.risk_score || 0)})
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
              <span>
                Counterparty: <strong className="text-slate-800">{item.counterparty || "—"}</strong>
              </span>
              <span>•</span>
              <span>
                Type: <strong className="text-slate-800 capitalize">{item.contract_type || "Vendor"}</strong>
              </span>
              <span>•</span>
              <span>
                Value: <strong className="text-slate-900">{formatCurrency(item.value_amount, item.value_currency)}</strong>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href={`/contracts/${item.contract_id}`}
              className="btn btn-secondary text-xs flex items-center gap-1 bg-white hover:bg-slate-50"
            >
              View Contract Details <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Sequential Workflow Steps Visualizer */}
      <div className="p-6 bg-slate-50/30">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Shield className="h-3.5 w-3.5 text-brand-600" /> Approval Workflow Progress
        </div>

        <div className="space-y-3">
          {steps.map((step: any, idx: number) => {
            const isCurrent = step.decision === "pending";
            const isApproved = step.decision === "approved";
            const isRejected = step.decision === "rejected";
            const isChanges = step.decision === "changes_requested";
            const isLocked = step.decision === "not_started";

            return (
              <div
                key={step.id || idx}
                className={`p-4 rounded-xl border transition-all ${
                  isCurrent
                    ? "bg-amber-50/40 border-amber-300 ring-2 ring-amber-400/20"
                    : isApproved
                    ? "bg-emerald-50/30 border-emerald-200"
                    : isRejected
                    ? "bg-rose-50/30 border-rose-200"
                    : isChanges
                    ? "bg-amber-50/20 border-amber-200"
                    : "bg-slate-100/60 border-slate-200/80 opacity-75"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="shrink-0">
                      {isApproved && <CheckCircle2 className="h-5 w-5 text-emerald-600" />}
                      {isCurrent && <Clock className="h-5 w-5 text-amber-600 animate-pulse" />}
                      {isLocked && <Lock className="h-5 w-5 text-slate-400" />}
                      {isRejected && <XCircle className="h-5 w-5 text-rose-600" />}
                      {isChanges && <RotateCcw className="h-5 w-5 text-amber-600" />}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-500">
                          Step {idx + 1} of {steps.length} —
                        </span>
                        <span className="text-sm font-semibold text-slate-900">
                          {step.step_name}
                        </span>
                        <span className="badge bg-white text-slate-600 border-slate-200 text-xs font-mono uppercase">
                          {step.required_role}
                        </span>
                      </div>

                      <div className="text-xs text-slate-500 mt-0.5">
                        {isApproved && (
                          <span className="text-emerald-700 font-medium">
                            Approved {step.decided_at ? `· ${formatDateTime(step.decided_at)}` : ""}
                          </span>
                        )}
                        {isCurrent && (
                          <span className="text-amber-800 font-medium flex items-center gap-1">
                            Waiting for active review {step.due_at ? `· Due ${formatDateTime(step.due_at)} (${relativeTime(step.due_at)})` : ""}
                          </span>
                        )}
                        {isLocked && (
                          <span className="text-slate-400 flex items-center gap-1">
                            <Lock className="h-3 w-3" /> Locked — Waiting for prior step completion
                          </span>
                        )}
                        {isRejected && <span className="text-rose-700 font-medium">Rejected</span>}
                        {isChanges && <span className="text-amber-800 font-medium">Changes Requested</span>}
                      </div>

                      {step.comments && (
                        <div className="text-xs text-slate-600 italic mt-1.5 bg-white/80 p-2 rounded-md border border-slate-200/60">
                          "{step.comments}"
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Show Action Buttons ONLY for Active Current Step */}
                  {isCurrent && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        className="btn btn-primary bg-emerald-600 hover:bg-emerald-700 text-white text-xs flex items-center gap-1 shadow-xs"
                        onClick={() => onOpenDecision("approved", step)}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                      </button>
                      <button
                        className="btn btn-secondary border-amber-300 text-amber-900 bg-amber-50 hover:bg-amber-100 text-xs flex items-center gap-1"
                        onClick={() => onOpenDecision("changes_requested", step)}
                      >
                        <RotateCcw className="h-3.5 w-3.5" /> Request Changes
                      </button>
                      <button
                        className="btn btn-danger bg-rose-600 hover:bg-rose-700 text-white text-xs flex items-center gap-1"
                        onClick={() => onOpenDecision("rejected", step)}
                      >
                        <XCircle className="h-3.5 w-3.5" /> Reject
                      </button>
                    </div>
                  )}

                  {isLocked && (
                    <span className="text-xs text-slate-400 font-medium bg-slate-200/60 px-3 py-1 rounded-full flex items-center gap-1">
                      <Lock className="h-3 w-3" /> Locked
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
