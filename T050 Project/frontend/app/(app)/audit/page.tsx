"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Shield, CheckCircle2 } from "lucide-react";
import { formatDateTime } from "@/lib/utils";
import { useState } from "react";

export default function AuditPage() {
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");
  const { data: entries } = useQuery({
    queryKey: ["audit", action, resourceType],
    queryFn: async () => (await api.get("/audit", {
      params: { action, resource_type: resourceType, limit: 200 }
    })).data,
  });
  const { data: verify } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
  });

  return (
    <div className="p-8 max-w-screen-2xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <Shield className="h-6 w-6 text-brand-600" />
            Audit Trail
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Tamper-evident SHA-256 hash chain. Every entry references the previous entry's hash.
          </p>
        </div>
        {verify && (
          <div className={`card px-4 py-3 flex items-center gap-2 ${verify.valid ? "border-emerald-200" : "border-rose-300 bg-rose-50"}`}>
            {verify.valid ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            ) : (
              <Shield className="h-4 w-4 text-rose-600" />
            )}
            <div>
              <div className={`text-sm font-semibold ${verify.valid ? "text-emerald-700" : "text-rose-700"}`}>
                {verify.valid ? "Chain intact" : "Chain broken"}
              </div>
              <div className="text-xs text-slate-500">{verify.total_entries} entries · {verify.message}</div>
            </div>
          </div>
        )}
      </div>

      <div className="card p-4 mb-4 flex flex-wrap gap-3">
        <select className="input w-auto" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">All actions</option>
          <option value="contract.create">contract.create</option>
          <option value="contract.version.upload">contract.version.upload</option>
          <option value="contract.analyze">contract.analyze</option>
          <option value="contract.submit_for_review">contract.submit_for_review</option>
          <option value="approval.decide">approval.decide</option>
          <option value="contract.activate">contract.activate</option>
          <option value="contract.renew">contract.renew</option>
          <option value="contract.archive">contract.archive</option>
          <option value="qa.ask">qa.ask</option>
          <option value="auth.login">auth.login</option>
        </select>
        <select className="input w-auto" value={resourceType} onChange={(e) => setResourceType(e.target.value)}>
          <option value="">All resources</option>
          <option value="contract">contract</option>
          <option value="contract_version">contract_version</option>
          <option value="approval">approval</option>
          <option value="obligation">obligation</option>
          <option value="user">user</option>
        </select>
      </div>

      <div className="card overflow-hidden">
        <div className="divide-y divide-slate-100">
          {(entries ?? []).map((e: any) => (
            <div key={e.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-slate-900">
                  <span className="text-slate-500">#{e.sequence}</span> {e.action}
                  <span className="text-slate-500 font-normal"> · {e.resource_type}{e.resource_id ? `(${e.resource_id.slice(0, 8)}…)` : ""}</span>
                </div>
                <div className="text-xs text-slate-500">
                  {formatDateTime(e.timestamp)} · {e.actor_email || "system"}
                </div>
              </div>
              {Object.keys(e.payload || {}).length > 0 && (
                <pre className="mt-2 text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              )}
              <div className="mt-2 text-xs text-slate-500 font-mono truncate">
                prev {e.previous_hash?.slice(0, 16)}… · entry {e.entry_hash?.slice(0, 16)}…
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
