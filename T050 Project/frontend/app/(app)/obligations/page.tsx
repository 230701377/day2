"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";
import { CheckCircle2 } from "lucide-react";
import { formatDate, severityColor } from "@/lib/utils";

export default function ObligationsPage() {
  const qc = useQueryClient();
  const { data: obligations } = useQuery({
    queryKey: ["obligations-all"],
    queryFn: async () => (await api.get("/obligations")).data,
  });

  const complete = useMutation({
    mutationFn: async (id: string) => (await api.post(`/obligations/${id}/complete`, {})).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["obligations-all"] }),
  });

  return (
    <div className="p-8 max-w-screen-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Obligations</h1>
        <p className="text-slate-500 text-sm mt-1">Action items extracted from your contracts.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {(obligations ?? []).map((o: any) => (
          <div key={o.id} className="card p-4">
            <div className="flex items-start justify-between mb-2">
              <Link href={`/contracts/${o.contract_id}`} className="font-medium text-slate-900 hover:text-brand-600">
                {o.title.slice(0, 90)}
              </Link>
              <span className={`badge ${severityColor(o.priority === "high" ? "high" : o.priority === "medium" ? "medium" : "low")}`}>
                {o.priority}
              </span>
            </div>
            <p className="text-sm text-slate-700 line-clamp-3 mb-3">{o.description}</p>
            <div className="flex items-center justify-between text-xs">
              <div className="text-slate-500">
                {o.due_date ? `Due ${formatDate(o.due_date)}` : "No deadline"} · {o.status}
              </div>
              {o.status !== "completed" ? (
                <button className="btn btn-secondary text-xs" onClick={() => complete.mutate(o.id)}>
                  <CheckCircle2 className="h-3 w-3" /> Complete
                </button>
              ) : (
                <span className="badge bg-emerald-100 text-emerald-800 border-emerald-200">completed</span>
              )}
            </div>
          </div>
        ))}
        {(!obligations || obligations.length === 0) && (
          <div className="col-span-full text-center text-slate-500 text-sm py-12">
            No obligations found. Run AI analyze on a contract to extract them.
          </div>
        )}
      </div>
    </div>
  );
}
