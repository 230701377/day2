"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { FileCode, ArrowRightLeft, Check, AlertCircle } from "lucide-react";

interface VersionDiffViewerProps {
  contractId: string;
  versions: any[];
}

export default function VersionDiffViewer({ contractId, versions }: VersionDiffViewerProps) {
  const [v1Id, setV1Id] = useState<string>(versions[1]?.id || versions[0]?.id || "");
  const [v2Id, setV2Id] = useState<string>(versions[0]?.id || "");

  const { data: diffData, isLoading } = useQuery({
    queryKey: ["version-diff", contractId, v1Id, v2Id],
    queryFn: async () => {
      if (!v1Id || !v2Id || v1Id === v2Id) return null;
      return (await api.get(`/contracts/${contractId}/compare`, {
        params: { v1: v1Id, v2: v2Id }
      })).data;
    },
    enabled: Boolean(v1Id && v2Id && v1Id !== v2Id),
  });

  if (versions.length < 2) {
    return (
      <div className="card p-8 text-center text-slate-500">
        <FileCode className="h-10 w-10 text-slate-300 mx-auto mb-2" />
        <div className="text-sm font-semibold">Multiple Versions Required for Diff</div>
        <div className="text-xs text-slate-400 mt-1">Upload a second contract version (amendment or draft) to unlock visual side-by-side diff comparison.</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Version Selector Bar */}
      <div className="card p-4 flex flex-wrap items-center justify-between gap-4 bg-slate-50/50">
        <div className="flex items-center gap-3">
          <ArrowRightLeft className="h-5 w-5 text-brand-600" />
          <span className="text-sm font-bold text-slate-900">Version Diff Comparison</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Base Version (v1):</span>
            <select
              className="input py-1 text-xs w-36"
              value={v1Id}
              onChange={(e) => setV1Id(e.target.value)}
            >
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  Version {v.version_number} ({v.version_label})
                </option>
              ))}
            </select>
          </div>

          <span className="text-slate-400 font-bold">vs</span>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Compare Version (v2):</span>
            <select
              className="input py-1 text-xs w-36"
              value={v2Id}
              onChange={(e) => setV2Id(e.target.value)}
            >
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  Version {v.version_number} ({v.version_label})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="card p-12 text-center text-slate-500">
          <div className="h-6 w-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
          <div className="text-xs font-medium">Computing semantic diff comparison...</div>
        </div>
      )}

      {diffData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card p-4 overflow-hidden border-l-4 border-l-slate-400">
            <div className="text-xs font-bold text-slate-600 uppercase mb-2 border-b pb-2 flex justify-between">
              <span>Base Version (v{diffData.v1_number || 1})</span>
              <span className="text-slate-400">{diffData.v1_label}</span>
            </div>
            <div
              className="text-xs font-mono leading-relaxed space-y-1 overflow-x-auto max-h-[500px] p-2 bg-slate-50 rounded"
              dangerouslySetInnerHTML={{ __html: diffData.html_v1 || diffData.raw_diff || "No changes detected." }}
            />
          </div>

          <div className="card p-4 overflow-hidden border-l-4 border-l-emerald-500">
            <div className="text-xs font-bold text-emerald-700 uppercase mb-2 border-b pb-2 flex justify-between">
              <span>Compared Version (v{diffData.v2_number || 2})</span>
              <span className="text-emerald-600">{diffData.v2_label}</span>
            </div>
            <div
              className="text-xs font-mono leading-relaxed space-y-1 overflow-x-auto max-h-[500px] p-2 bg-emerald-50/20 rounded"
              dangerouslySetInnerHTML={{ __html: diffData.html_v2 || diffData.raw_diff || "No changes detected." }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
