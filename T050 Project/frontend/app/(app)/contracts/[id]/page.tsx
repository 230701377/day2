"use client";

import { useMemo } from "react";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  Upload, Sparkles, FileText, History, ArrowLeftRight, Shield,
  AlertCircle, ListChecks, MessageSquare, GitCompare, Plus, Calendar, Trash2
} from "lucide-react";
import {
  formatCurrency, formatDate, formatDateTime, relativeTime,
  statusColor, riskColor, severityColor,
} from "@/lib/utils";

import VersionDiffViewer from "@/components/VersionDiffViewer";

type Tab = "analysis" | "clauses" | "risks" | "obligations" | "approvals" | "versions" | "audit" | "qa";

export default function ContractDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [tab, setTab] = useState<Tab>("analysis");
  const qc = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const { data: contract } = useQuery({
    queryKey: ["contract", id],
    queryFn: async () => (await api.get(`/contracts/${id}`)).data,
    refetchInterval: (query: any) => {
      const data = query.state.data;
      if (data?.processing_status === "PROCESSING" || data?.processing_status === "QUEUED") {
        return 2000;
      }
      return false;
    }
  });

  const retryAnalysis = useMutation({
    mutationFn: async () => (await api.post(`/contracts/${id}/retry-analysis`)).data,
    onSuccess: () => {
      toast.success("AI Analysis re-queued!");
      qc.invalidateQueries({ queryKey: ["contract", id] });
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Retry failed")),
  });
  const { data: versions } = useQuery({
    queryKey: ["versions", id],
    queryFn: async () => (await api.get(`/contracts/${id}/versions`)).data,
  });
  const { data: clauses } = useQuery({
    queryKey: ["clauses", id],
    queryFn: async () => (await api.get(`/ai/clauses/${id}`)).data,
  });
  const { data: risks } = useQuery({
    queryKey: ["risks", id],
    queryFn: async () => (await api.get(`/ai/risks/${id}`)).data,
  });
  const { data: obligations } = useQuery({
    queryKey: ["obligations", id],
    queryFn: async () => (await api.get(`/obligations`, { params: { contract_id: id } })).data,
  });
  const { data: approvals } = useQuery({
    queryKey: ["approvals", id],
    queryFn: async () => (await api.get(`/approvals/contract/${id}`)).data,
  });
  const { data: audit } = useQuery({
    queryKey: ["audit-contract", id],
    queryFn: async () => (await api.get(`/audit/contract/${id}`)).data,
    enabled: tab === "audit",
  });

  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const latestVersion = versions?.[0];

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return (await api.post(`/contracts/${id}/versions`, fd)).data;
    },
    onSuccess: () => {
      toast.success("Version uploaded");
      qc.invalidateQueries({ queryKey: ["versions", id] });
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Upload failed")),
  });

  const analyze = useMutation({
    mutationFn: async (versionId: string) =>
      (await api.post(`/ai/analyze/${id}/${versionId}`)).data,
    onSuccess: () => {
      toast.success("Analysis complete");
      qc.invalidateQueries({ queryKey: ["clauses", id] });
      qc.invalidateQueries({ queryKey: ["risks", id] });
      qc.invalidateQueries({ queryKey: ["obligations", id] });
      qc.invalidateQueries({ queryKey: ["contract", id] });
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Analysis failed")),
  });

  const submit = useMutation({
    mutationFn: async () => (await api.post(`/contracts/${id}/submit-for-review`)).data,
    onSuccess: () => {
      toast.success("Submitted for review");
      qc.invalidateQueries({ queryKey: ["approvals", id] });
      qc.invalidateQueries({ queryKey: ["contract", id] });
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Submission failed")),
  });

  const handleSubmitForApproval = () => {
    if (!latestVersion && (!versions || versions.length === 0)) {
      toast.error("Please upload a contract document (.pdf, .docx, or .txt) first so reviewers have a version to evaluate.");
      fileInput.current?.click();
      return;
    }
    submit.mutate();
  };

  const activate = useMutation({
    mutationFn: async () => (await api.post(`/contracts/${id}/activate`)).data,
    onSuccess: () => {
      toast.success("Contract activated");
      qc.invalidateQueries({ queryKey: ["contract", id] });
    },
  });

  const archive = useMutation({
    mutationFn: async () => (await api.post(`/contracts/${id}/archive`)).data,
    onSuccess: () => {
      toast.success("Archived");
      qc.invalidateQueries({ queryKey: ["contract", id] });
    },
  });

  const renew = useMutation({
    mutationFn: async () => (await api.post(`/contracts/${id}/renew`)).data,
    onSuccess: (c) => {
      toast.success("Renewal created");
      window.location.href = `/contracts/${c.id}`;
    },
  });

  const deleteContract = useMutation({
    mutationFn: async () => (await api.delete(`/contracts/${id}`)).data,
    onSuccess: (data: any) => {
      toast.success(data.message || "Contract deleted");
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
      window.location.href = "/contracts";
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Delete failed")),
  });

  const [analysisData, setAnalysisData] = useState<any>(null);
  const analyzeWithData = useMutation({
    mutationFn: async (versionId: string) =>
      (await api.post(`/ai/analyze/${id}/${versionId}`)).data,
    onSuccess: (data) => setAnalysisData(data),
    onError: (e: any) => toast.error(getErrorMessage(e, "Analysis failed")),
  });

  // Build an analysis-like object from the data already in the DB so the
  // AI Analysis tab shows real content even when the user has not clicked
  // the "AI analyze" button on this visit. This makes seeded/older contracts
  // instantly readable.
  const composedAnalysis = useMemo<any>(() => {
    if (!contract || !latestVersion) return null;
    if (!clauses && !risks && !obligations) return null;
    return {
      contract_id: contract.id,
      version_id: latestVersion.id,
      status: "complete",
      summary: latestVersion.change_summary || null,
      metadata: {},
      clauses: clauses ?? [],
      risks: risks ?? [],
      risk_score: contract.risk_score ?? 0,
      risk_level: contract.risk_level ?? "low",
      missing_clauses: [],
      template_deviation: [],
      obligations: (obligations ?? []).map((o: any) => ({
        title: o.title, description: o.description,
        category: o.responsible_role, priority: o.priority,
      })),
      version_comparison: null,
    };
  }, [contract, latestVersion, clauses, risks, obligations]);

  // Show fresh AI analysis when user just clicked AI analyze, otherwise
  // fall back to the data composed from existing DB records.
  const displayAnalysis = analysisData ?? composedAnalysis;

  if (!contract) return <div className="p-8 text-slate-500">Loading...</div>;

  return (
    <div className="p-8 max-w-screen-2xl mx-auto">
      <div className="mb-4">
        <Link href="/contracts" className="text-xs text-slate-500 hover:text-brand-600">← Back to contracts</Link>
      </div>

      {contract?.processing_status === "PROCESSING" || contract?.processing_status === "QUEUED" ? (
        <div className="card p-5 mb-6 bg-gradient-to-r from-blue-50 via-indigo-50 to-slate-50 border border-blue-200 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-3.5 h-3.5 rounded-full bg-blue-600 animate-ping"></div>
              <h3 className="font-semibold text-blue-950 text-base">
                AI Document Intelligence Pipeline Active: {contract?.processing_step || "Processing..."}
              </h3>
            </div>
            <span className="text-xs font-bold text-blue-700 bg-blue-100 px-3 py-1 rounded-full border border-blue-200">
              {contract?.processing_progress || 10}% Complete
            </span>
          </div>

          <div className="w-full bg-blue-100 rounded-full h-2 mb-4 overflow-hidden">
            <div
              className="bg-brand-600 h-2 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${contract?.processing_progress || 10}%` }}
            ></div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 text-xs">
            <div className={`p-2.5 rounded-lg border ${ (contract?.processing_progress || 0) >= 25 ? 'bg-white text-emerald-800 border-emerald-200 font-semibold shadow-xs' : 'bg-white/60 text-slate-400 border-slate-200' } flex items-center gap-1.5`}>
              {(contract?.processing_progress || 0) >= 25 ? '✓' : '⟳'} Document Text
            </div>
            <div className={`p-2.5 rounded-lg border ${ (contract?.processing_progress || 0) >= 45 ? 'bg-white text-emerald-800 border-emerald-200 font-semibold shadow-xs' : 'bg-white/60 text-slate-400 border-slate-200' } flex items-center gap-1.5`}>
              {(contract?.processing_progress || 0) >= 45 ? '✓' : '⟳'} AI Classification
            </div>
            <div className={`p-2.5 rounded-lg border ${ (contract?.processing_progress || 0) >= 60 ? 'bg-white text-emerald-800 border-emerald-200 font-semibold shadow-xs' : 'bg-white/60 text-slate-400 border-slate-200' } flex items-center gap-1.5`}>
              {(contract?.processing_progress || 0) >= 60 ? '✓' : '⟳'} Duplicate Check
            </div>
            <div className={`p-2.5 rounded-lg border ${ (contract?.processing_progress || 0) >= 75 ? 'bg-white text-emerald-800 border-emerald-200 font-semibold shadow-xs' : 'bg-white/60 text-slate-400 border-slate-200' } flex items-center gap-1.5`}>
              {(contract?.processing_progress || 0) >= 75 ? '✓' : '⟳'} Vector Embeddings
            </div>
            <div className={`p-2.5 rounded-lg border ${ (contract?.processing_progress || 0) >= 85 ? 'bg-white text-emerald-800 border-emerald-200 font-semibold shadow-xs' : 'bg-white/60 text-slate-400 border-slate-200' } flex items-center gap-1.5`}>
              {(contract?.processing_progress || 0) >= 85 ? '✓' : '⟳'} Risk Scoring
            </div>
            <div className={`p-2.5 rounded-lg border ${ (contract?.processing_progress || 0) >= 95 ? 'bg-white text-emerald-800 border-emerald-200 font-semibold shadow-xs' : 'bg-white/60 text-slate-400 border-slate-200' } flex items-center gap-1.5`}>
              {(contract?.processing_progress || 0) >= 95 ? '✓' : '⟳'} Approval Workflow
            </div>
          </div>
        </div>
      ) : contract?.processing_status === "FAILED" ? (
        <div className="card p-5 mb-6 bg-red-50 border border-red-200 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-red-950 text-sm">AI Analysis Encountered an Issue</h3>
            <p className="text-xs text-red-700 mt-1">{contract?.processing_error || "An error occurred during background document analysis."}</p>
          </div>
          <button
            onClick={() => retryAnalysis.mutate()}
            disabled={retryAnalysis.isPending}
            className="btn btn-primary bg-red-600 hover:bg-red-700 text-white text-xs"
          >
            {retryAnalysis.isPending ? "Re-queuing..." : "Retry Analysis"}
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">{contract.title}</h1>
            <span className="badge bg-indigo-50 text-indigo-700 border-indigo-200 text-xs font-bold">
              {contract.contract_type === "vendor" ? "Vendor Contract" :
               contract.contract_type === "supplier" ? "Supplier Contract" :
               contract.contract_type === "license" ? "Customer / SaaS Contract" :
               contract.contract_type === "partnership" ? "Business Partner Contract" : "Vendor Contract"}
            </span>
            <span className={`badge ${statusColor(contract.status)}`}>{contract.status.replace("_", " ")}</span>
            <span className={`badge ${riskColor(contract.risk_level)}`}>
              Risk: {contract.risk_level} ({Math.round(contract.risk_score)})
            </span>
          </div>
          <div className="text-sm text-slate-500 mt-1">
            {contract.contract_number} · Category: {contract.contract_type.toUpperCase()} ·
            {" "}Counterparty: {contract.counterparty || "—"} · {formatCurrency(contract.value_amount, contract.value_currency)}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            type="file" ref={fileInput} className="hidden"
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])}
          />
          <button className="btn btn-secondary" onClick={() => fileInput.current?.click()}>
            <Upload className="h-4 w-4" /> Upload version
          </button>
          {latestVersion && (
            <button
              className="btn btn-primary"
              onClick={() => analyzeWithData.mutate(latestVersion.id)}
              disabled={analyzeWithData.isPending}
            >
              <Sparkles className="h-4 w-4" />
              {analyzeWithData.isPending ? "Analyzing..." : "AI analyze"}
            </button>
          )}
          {["draft", "analysis_complete", "changes_requested", "rejected"].includes(contract.status) && (
            <button
              className="btn btn-primary bg-indigo-600 hover:bg-indigo-700 text-white font-medium shadow-sm"
              onClick={handleSubmitForApproval}
              disabled={submit.isPending}
            >
              <ListChecks className="h-4 w-4" /> {submit.isPending ? "Submitting..." : "Submit for Approval"}
            </button>
          )}
          {contract.status === "approved" && (
            <button className="btn btn-primary" onClick={() => activate.mutate()}>
              <Shield className="h-4 w-4" /> Activate
            </button>
          )}
          {contract.expiration_date && (
            <button className="btn btn-secondary" onClick={() => renew.mutate()}>
              <Calendar className="h-4 w-4" /> Renew
            </button>
          )}
          <a
            className="btn btn-secondary border-brand-300 text-brand-700 bg-brand-50/50 hover:bg-brand-100"
            href={`/api/proxy/signatures/${id}/certificate`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Shield className="h-4 w-4 text-brand-600" /> Certificate
          </a>
          {contract.status !== "archived" && (
            <button className="btn btn-ghost" onClick={() => archive.mutate()}>Archive</button>
          )}
          <button
            className="btn bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 text-xs font-semibold"
            onClick={() => {
              if (confirm(`Are you sure you want to permanently delete "${contract?.title}"?`)) {
                deleteContract.mutate();
              }
            }}
            disabled={deleteContract.isPending}
          >
            <Trash2 className="h-4 w-4 text-red-600" />
            {deleteContract.isPending ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>

      <div className="card overflow-hidden mb-6">
        <div className="border-b border-slate-200 px-5">
          <nav className="flex gap-1 overflow-x-auto">
            {([
              ["analysis", "AI analysis", Sparkles],
              ["clauses", `Clauses (${clauses?.length ?? 0})`, FileText],
              ["risks", `Risks (${risks?.length ?? 0})`, AlertCircle],
              ["obligations", `Obligations (${obligations?.length ?? 0})`, ListChecks],
              ["approvals", `Approvals (${approvals?.length ?? 0})`, Shield],
              ["versions", `Versions (${versions?.length ?? 0})`, History],
              ["audit", "Audit trail", FileText],
              ["qa", "Q&A", MessageSquare],
            ] as [Tab, string, any][]).map(([k, label, Icon]) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                className={`px-4 py-3 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
                  tab === k
                    ? "border-brand-600 text-brand-600 font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {tab === "analysis" && (
            <AnalysisView
              data={displayAnalysis}
              contract={contract}
              hasVersion={Boolean(latestVersion || (versions && versions.length > 0))}
              onUploadClick={() => fileInput.current?.click()}
            />
          )}
          {tab === "clauses" && (
            <ClausesView clauses={clauses ?? []} versionId={selectedVersionId ?? latestVersion?.id} />
          )}
          {tab === "risks" && <RisksView risks={risks ?? []} />}
          {tab === "obligations" && <ObligationsView obligations={obligations ?? []} />}
          {tab === "approvals" && <ApprovalsView approvals={approvals ?? []} contractId={id} />}
          {tab === "versions" && (
            <VersionsView
              contractId={id}
              versions={versions ?? []}
              onCompare={(a, b) => api.get(`/ai/compare/${id}`, { params: { from_version: a, to_version: b } }).then((r) => r.data)}
            />
          )}
          {tab === "audit" && <AuditView entries={audit ?? []} />}
          {tab === "qa" && <QAView contractId={id} />}
        </div>
      </div>
    </div>
  );
}

function AnalysisView({
  data,
  contract,
  hasVersion = true,
  onUploadClick,
}: {
  data: any;
  contract: any;
  hasVersion?: boolean;
  onUploadClick?: () => void;
}) {
  if (!data) {
    if (!hasVersion) {
      return (
        <div className="text-center py-12">
          <div className="w-12 h-12 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto mb-3 text-indigo-600">
            <Upload className="h-6 w-6" />
          </div>
          <div className="text-slate-800 font-semibold text-base">No Contract Document Uploaded Yet</div>
          <div className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
            To submit this contract for approval or run AI analysis, please upload the agreement document (.pdf, .docx, or .txt).
          </div>
          {onUploadClick && (
            <button
              onClick={onUploadClick}
              className="btn btn-primary bg-indigo-600 hover:bg-indigo-700 text-white font-medium mt-4 inline-flex items-center gap-2"
            >
              <Upload className="h-4 w-4" /> Upload Document Version
            </button>
          )}
        </div>
      );
    }
    return (
      <div className="text-center py-12">
        <Sparkles className="h-10 w-10 mx-auto text-slate-300 mb-3" />
        <div className="text-slate-700 font-medium">No analysis yet</div>
        <div className="text-sm text-slate-500 mt-1">
          Click <span className="font-semibold">AI analyze</span> to extract clauses, classify them,
          detect risks, summarize and surface obligations.
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="section-title">Risk score</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-900">{Math.round(data.risk_score)}</span>
            <span className={`badge ${riskColor(data.risk_level)}`}>{data.risk_level}</span>
          </div>
          <div className="mt-3 h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full ${
                data.risk_level === "critical" ? "bg-red-600" :
                data.risk_level === "high" ? "bg-rose-500" :
                data.risk_level === "medium" ? "bg-amber-500" : "bg-emerald-500"
              }`}
              style={{ width: `${Math.min(100, data.risk_score)}%` }}
            />
          </div>
        </div>
        <div className="card p-4">
          <div className="section-title">Clauses extracted</div>
          <div className="text-3xl font-bold mt-2">{data.clauses?.length ?? 0}</div>
          <div className="text-xs text-slate-500 mt-1">
            Avg. confidence {(
              (data.clauses?.reduce((s: number, c: any) => s + (c.confidence || 0), 0) || 0) /
              Math.max(1, data.clauses?.length || 1)
            ).toFixed(2)}
          </div>
        </div>
        <div className="card p-4">
          <div className="section-title">Findings</div>
          <div className="text-3xl font-bold mt-2">{data.risks?.length ?? 0}</div>
          <div className="text-xs text-slate-500 mt-1">
            {data.risks?.filter((r: any) => r.severity === "critical" || r.severity === "high").length ?? 0} high / critical
          </div>
        </div>
      </div>

      <div className="card p-5">
        <div className="section-title mb-2">Executive summary</div>
        <p className="text-slate-700 leading-relaxed">{data.summary}</p>
      </div>

      {data.metadata && Object.keys(data.metadata).length > 0 && (
        <div className="card p-5">
          <div className="section-title mb-3">Extracted metadata</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            {Object.entries(data.metadata).map(([k, v]) => (
              v ? (
                <div key={k}>
                  <div className="text-xs text-slate-500 capitalize">{k.replace(/_/g, " ")}</div>
                  <div className="text-slate-900 mt-0.5">{String(v)}</div>
                </div>
              ) : null
            ))}
          </div>
        </div>
      )}

      {data.missing_clauses?.length > 0 && (
        <div className="card p-5 border-amber-200 bg-amber-50">
          <div className="section-title mb-2 text-amber-700">Missing clauses (vs template)</div>
          <ul className="space-y-1 text-sm">
            {data.missing_clauses.map((m: any, i: number) => (
              <li key={i} className="text-amber-900">
                <span className="font-medium capitalize">{m.category.replace(/_/g, " ")}</span>
                {" — "}{m.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ClausesView({ clauses, versionId }: { clauses: any[]; versionId?: string }) {
  const filtered = clauses.filter((c) => !versionId || c.version_id === versionId);
  const [activeCat, setActiveCat] = useState<string>("all");
  const cats = ["all", ...Array.from(new Set(filtered.map((c) => c.category || "uncategorized")))];
  const shown = filtered.filter((c) => activeCat === "all" || (c.category || "uncategorized") === activeCat);
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        {cats.map((c) => (
          <button
            key={c}
            className={`px-3 py-1 rounded-full text-xs font-medium border ${
              activeCat === c ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
            }`}
            onClick={() => setActiveCat(c)}
          >
            {c.replace(/_/g, " ")} ({filtered.filter((x) => (c === "all" || (x.category || "uncategorized") === c)).length})
          </button>
        ))}
      </div>
      <div className="space-y-3">
        {shown.map((c) => (
          <div key={c.id} className="border border-slate-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-slate-900">
                {c.clause_number}. {c.heading || "Clause"}
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="badge bg-slate-100 text-slate-700 border-slate-200">
                  {c.category?.replace(/_/g, " ") || "uncategorized"}
                </span>
                <span className="text-slate-400">conf {c.confidence.toFixed(2)}</span>
                {c.page_number && <span className="text-slate-400">page {c.page_number}</span>}
              </div>
            </div>
            <p className="text-sm text-slate-700 whitespace-pre-wrap line-clamp-6">{c.body}</p>
          </div>
        ))}
        {shown.length === 0 && (
          <div className="text-center text-slate-500 text-sm py-10">No clauses extracted yet.</div>
        )}
      </div>
    </div>
  );
}

function RisksView({ risks }: { risks: any[] }) {
  return (
    <div className="space-y-3">
      {risks.length === 0 && (
        <div className="text-center text-slate-500 text-sm py-10">No risks detected.</div>
      )}
      {risks.map((r) => (
        <div key={r.id} className="border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="font-semibold text-slate-900">{r.title}</div>
            <div className="flex items-center gap-2 text-xs">
              <span className={`badge ${severityColor(r.severity)}`}>{r.severity}</span>
              <span className="text-slate-400">score {r.score_total.toFixed(2)}</span>
              {r.source_page && <span className="text-slate-400">page {r.source_page}</span>}
            </div>
          </div>
          <p className="text-sm text-slate-700 mb-2">{r.description}</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <ScoreBar label="Rule" value={r.score_rule} max={4} />
            <ScoreBar label="NLP" value={r.score_nlp} max={4} />
            <ScoreBar label="LLM" value={r.score_llm} max={4} />
          </div>
          {r.recommendation && (
            <div className="mt-3 p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-900 text-sm">
              <strong>Recommendation:</strong> {r.recommendation}
            </div>
          )}
          {r.source_excerpt && (
            <div className="mt-3 p-3 rounded-md bg-slate-50 border border-slate-200 text-slate-700 text-xs italic">
              "{r.source_excerpt}"
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-500 mb-1">
        <span>{label}</span><span>{value.toFixed(2)} / {max}</span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ObligationsView({ obligations }: { obligations: any[] }) {
  const qc = useQueryClient();
  const complete = useMutation({
    mutationFn: async (id: string) => (await api.post(`/obligations/${id}/complete`, {})).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["obligations"] }),
  });
  return (
    <div className="space-y-3">
      {obligations.length === 0 && (
        <div className="text-center text-slate-500 text-sm py-10">No obligations extracted.</div>
      )}
      {obligations.map((o) => (
        <div key={o.id} className="border border-slate-200 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="min-w-0">
              <div className="font-semibold text-slate-900">{o.title}</div>
              <p className="text-sm text-slate-700 mt-1 line-clamp-3">{o.description}</p>
            </div>
            <div className="shrink-0 ml-3 flex flex-col items-end gap-2">
              <span className={`badge ${severityColor(o.priority === "high" ? "high" : o.priority === "medium" ? "medium" : "low")}`}>
                {o.priority}
              </span>
              {o.status !== "completed" && (
                <button className="btn btn-secondary text-xs" onClick={() => complete.mutate(o.id)}>
                  Mark complete
                </button>
              )}
              {o.status === "completed" && (
                <span className="badge bg-emerald-100 text-emerald-800 border-emerald-200">completed</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ApprovalsView({ approvals, contractId }: { approvals: any[]; contractId: string }) {
  const qc = useQueryClient();
  const [activeStep, setActiveStep] = useState<any>(null);
  const [decisionModal, setDecisionModal] = useState<"approved" | "rejected" | "changes_requested" | null>(null);
  const [comments, setComments] = useState("");

  const decide = useMutation({
    mutationFn: async ({ id, decision, comments }: { id: string; decision: string; comments: string }) =>
      (await api.post(`/approvals/${id}/decide`, { decision, comments })).data,
    onSuccess: () => {
      toast.success("Decision recorded successfully");
      qc.invalidateQueries({ queryKey: ["approvals", contractId] });
      qc.invalidateQueries({ queryKey: ["contract", contractId] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
      closeModal();
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Decision failed")),
  });

  const closeModal = () => {
    setActiveStep(null);
    setDecisionModal(null);
    setComments("");
  };

  const handleConfirm = () => {
    if (!activeStep || !decisionModal) return;
    if ((decisionModal === "rejected" || decisionModal === "changes_requested") && !comments.trim()) {
      toast.error("Please provide a reason or comment.");
      return;
    }
    decide.mutate({ id: activeStep.id, decision: decisionModal, comments: comments.trim() });
  };

  return (
    <div className="space-y-4">
      {approvals.length === 0 && (
        <div className="text-center text-slate-500 text-sm py-12">
          No approval workflow steps initialized yet. Click <strong>Submit for review</strong> above.
        </div>
      )}

      {approvals.map((a, idx) => {
        const isCurrent = a.decision === "pending";
        const isApproved = a.decision === "approved";
        const isRejected = a.decision === "rejected";
        const isChanges = a.decision === "changes_requested";
        const isLocked = a.decision === "not_started";

        return (
          <div
            key={a.id}
            className={`p-4 rounded-xl border transition ${
              isCurrent
                ? "bg-amber-50/50 border-amber-300 ring-2 ring-amber-400/20"
                : isApproved
                ? "bg-emerald-50/30 border-emerald-200"
                : isRejected
                ? "bg-rose-50/30 border-rose-200"
                : isChanges
                ? "bg-amber-50/20 border-amber-200"
                : "bg-slate-100/60 border-slate-200 opacity-75"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-500">Step {idx + 1} of {approvals.length} —</span>
                  <span className="font-semibold text-slate-900">{a.step_name}</span>
                  <span className="badge bg-white text-slate-600 border-slate-200 text-xs">{a.required_role}</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {isApproved && <span className="text-emerald-700 font-medium">✓ Approved · {formatDateTime(a.decided_at || a.created_at)}</span>}
                  {isCurrent && <span className="text-amber-800 font-medium">⏳ Active Review Step · SLA {a.sla_hours}h · Due {formatDateTime(a.due_at)} ({relativeTime(a.due_at)})</span>}
                  {isLocked && <span className="text-slate-400">🔒 Locked — Waiting for previous approval</span>}
                  {isRejected && <span className="text-rose-700 font-medium">✕ Rejected</span>}
                  {isChanges && <span className="text-amber-800 font-medium">↩ Changes Requested</span>}
                </div>
                {a.comments && (
                  <div className="text-xs text-slate-600 italic mt-1.5 bg-white p-2 rounded border border-slate-200/60">
                    "{a.comments}"
                  </div>
                )}
              </div>

              {isCurrent && (
                <div className="flex items-center gap-2">
                  <button
                    className="btn btn-primary bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                    onClick={() => { setActiveStep(a); setDecisionModal("approved"); }}
                  >
                    Approve
                  </button>
                  <button
                    className="btn btn-secondary border-amber-300 text-amber-900 bg-amber-50 hover:bg-amber-100 text-xs"
                    onClick={() => { setActiveStep(a); setDecisionModal("changes_requested"); }}
                  >
                    Request Changes
                  </button>
                  <button
                    className="btn btn-danger bg-rose-600 hover:bg-rose-700 text-white text-xs"
                    onClick={() => { setActiveStep(a); setDecisionModal("rejected"); }}
                  >
                    Reject
                  </button>
                </div>
              )}

              {isLocked && (
                <span className="text-xs text-slate-400 bg-slate-200/60 px-3 py-1 rounded-full">
                  🔒 Locked
                </span>
              )}
            </div>
          </div>
        );
      })}

      {/* Decision Modal */}
      {decisionModal && activeStep && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-100">
            <h3 className="text-base font-bold text-slate-900 mb-2">
              {decisionModal === "approved" && "Approve Contract Step"}
              {decisionModal === "rejected" && "Reject Contract"}
              {decisionModal === "changes_requested" && "Request Contract Changes"}
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Step: {activeStep.step_name} ({activeStep.required_role})
            </p>
            <textarea
              rows={3}
              className="input text-xs w-full p-3 mb-4 resize-none"
              placeholder={decisionModal === "approved" ? "Optional approval notes..." : "Enter reason / feedback..."}
              value={comments}
              onChange={(e) => setComments(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button className="btn btn-secondary text-xs" onClick={closeModal}>Cancel</button>
              <button
                className={`btn text-xs ${
                  decisionModal === "approved" ? "btn-primary bg-emerald-600 text-white" :
                  decisionModal === "rejected" ? "btn-danger bg-rose-600 text-white" : "bg-amber-600 text-white"
                }`}
                onClick={handleConfirm}
                disabled={decide.isPending}
              >
                {decide.isPending ? "Submitting..." : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function VersionsView({
  contractId, versions, onCompare,
}: { contractId: string; versions: any[]; onCompare: (a: number, b: number) => Promise<any> }) {
  const [v1, setV1] = useState<number | null>(null);
  const [v2, setV2] = useState<number | null>(null);
  const [diff, setDiff] = useState<any>(null);
  return (
    <div className="space-y-6">
      <VersionDiffViewer contractId={contractId} versions={versions} />
      <div className="card p-4 mb-4">
        <div className="section-title mb-2 flex items-center gap-2"><GitCompare className="h-4 w-4" /> Compare versions</div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="label">From</label>
            <select className="input w-32" value={v1 ?? ""} onChange={(e) => setV1(Number(e.target.value))}>
              <option value="">select</option>
              {versions.map((v) => <option key={v.id} value={v.version_number}>v{v.version_number}</option>)}
            </select>
          </div>
          <div>
            <label className="label">To</label>
            <select className="input w-32" value={v2 ?? ""} onChange={(e) => setV2(Number(e.target.value))}>
              <option value="">select</option>
              {versions.map((v) => <option key={v.id} value={v.version_number}>v{v.version_number}</option>)}
            </select>
          </div>
          <button
            className="btn btn-primary"
            disabled={!v1 || !v2}
            onClick={async () => {
              const r = await onCompare(v1!, v2!);
              setDiff(r);
            }}
          >
            Compare
          </button>
        </div>
      </div>

      <div className="card overflow-hidden mb-4">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-xs uppercase">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">Version</th>
              <th className="text-left px-4 py-3 font-semibold">Label</th>
              <th className="text-left px-4 py-3 font-semibold">Filename</th>
              <th className="text-left px-4 py-3 font-semibold">Pages</th>
              <th className="text-left px-4 py-3 font-semibold">SHA-256</th>
              <th className="text-left px-4 py-3 font-semibold">Uploaded</th>
              <th className="text-left px-4 py-3 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {versions.map((v) => (
              <tr key={v.id}>
                <td className="px-4 py-3 font-medium">v{v.version_number}</td>
                <td className="px-4 py-3 text-slate-700">{v.version_label || "—"}</td>
                <td className="px-4 py-3 text-slate-700 truncate max-w-[200px]">{v.original_filename}</td>
                <td className="px-4 py-3">{v.page_count ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500 truncate max-w-[180px]">{v.sha256_hash.slice(0, 16)}…</td>
                <td className="px-4 py-3 text-slate-500">{formatDateTime(v.created_at)}</td>
                <td className="px-4 py-3">
                  <a className="text-brand-600 hover:underline text-xs"
                     href={`/api/proxy/contracts/${contractId}/versions/${v.id}/download`}
                     target="_blank" rel="noopener noreferrer">
                    Download
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {diff && (
        <div className="space-y-3">
          <div className="card p-4">
            <div className="section-title mb-1">Comparison summary</div>
            <p className="text-sm text-slate-700">{diff.summary}</p>
            <div className="mt-2 text-xs">
              Risk delta: <span className={diff.risk_delta > 0 ? "text-rose-600 font-medium" : "text-emerald-600 font-medium"}>
                {diff.risk_delta > 0 ? "+" : ""}{diff.risk_delta}
              </span>
            </div>
          </div>
          {diff.modified_clauses?.length > 0 && diff.modified_clauses.map((m: any, i: number) => (
            <div key={i} className="card p-4">
              <div className="font-semibold mb-1">
                {m.clause_number}. {m.heading}
              </div>
              <div className="text-xs text-slate-500 mb-2">
                similarity {(m.similarity * 100).toFixed(1)}% · risk changed: {m.risk_changed ? "yes" : "no"}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-md bg-rose-50 border border-rose-200 text-xs whitespace-pre-wrap">
                  <div className="font-semibold text-rose-800 mb-1">Previous</div>
                  {m.preview.from}
                </div>
                <div className="p-3 rounded-md bg-emerald-50 border border-emerald-200 text-xs whitespace-pre-wrap">
                  <div className="font-semibold text-emerald-800 mb-1">New</div>
                  {m.preview.to}
                </div>
              </div>
            </div>
          ))}
          {diff.added_clauses?.length > 0 && (
            <div className="card p-4">
              <div className="section-title mb-2 text-emerald-700">Added</div>
              <ul className="space-y-1 text-sm">
                {diff.added_clauses.map((a: any, i: number) => (
                  <li key={i}><strong>{a.clause_number}. {a.heading}</strong> — {a.preview}</li>
                ))}
              </ul>
            </div>
          )}
          {diff.removed_clauses?.length > 0 && (
            <div className="card p-4">
              <div className="section-title mb-2 text-rose-700">Removed</div>
              <ul className="space-y-1 text-sm">
                {diff.removed_clauses.map((a: any, i: number) => (
                  <li key={i}><strong>{a.clause_number}. {a.heading}</strong> — {a.preview}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AuditView({ entries }: { entries: any[] }) {
  return (
    <div className="space-y-2">
      {entries.length === 0 && (
        <div className="text-center text-slate-500 text-sm py-10">No audit entries for this contract.</div>
      )}
      {entries.map((e) => (
        <div key={e.id} className="border border-slate-200 rounded-lg p-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-slate-900">
              <span className="text-slate-500">#{e.sequence}</span> {e.action}
            </div>
            <div className="text-xs text-slate-500">
              {formatDateTime(e.timestamp)} · {e.actor_email || "system"}
            </div>
          </div>
          {Object.keys(e.payload || {}).length > 0 && (
            <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 mt-2 overflow-x-auto">
              {JSON.stringify(e.payload, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

function QAView({ contractId }: { contractId: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  async function ask() {
    if (!question.trim()) return;
    setBusy(true);
    try {
      const r = await api.post("/qa/ask", { question, contract_ids: [contractId], top_k: 5 });
      setAnswer(r.data);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="card p-4 mb-4">
        <label className="label">Ask anything about this contract</label>
        <div className="flex gap-2">
          <input
            className="input"
            placeholder="e.g. What is the liability cap?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
          />
          <button className="btn btn-primary" onClick={ask} disabled={busy}>
            {busy ? "Thinking..." : "Ask"}
          </button>
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Answers are grounded only in this contract's clauses. Sources are cited.
        </div>
      </div>
      {answer && (
        <div className="card p-5">
          <div className="section-title mb-2">Answer</div>
          <div className="text-slate-900 whitespace-pre-wrap text-sm">{answer.answer}</div>
          <div className="text-xs text-slate-500 mt-2">Confidence: {(answer.confidence * 100).toFixed(1)}%</div>
          {answer.sources?.length > 0 && (
            <div className="mt-4">
              <div className="section-title mb-2">Sources</div>
              <div className="space-y-2">
                {answer.sources.map((s: any, i: number) => (
                  <div key={i} className="border border-slate-200 rounded-md p-3">
                    <div className="text-xs text-slate-500 mb-1">
                      Clause {s.heading || s.clause_id?.slice(0, 8)} · page {s.page_number ?? "?"} · score {(s.score * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-slate-700 italic">"{s.excerpt}"</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
