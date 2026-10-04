"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage } from "@/lib/api";
import toast from "react-hot-toast";
import { Plus, Shield } from "lucide-react";
import { roleLabel, formatDateTime } from "@/lib/utils";
import { useState } from "react";

export default function UsersAdminPage() {
  const qc = useQueryClient();
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/auth/users")).data,
  });
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<any>({
    email: "", full_name: "", password: "Demo1234!", role: "requester", department: "",
  });

  const create = useMutation({
    mutationFn: async (p: any) => (await api.post("/auth/users", p)).data,
    onSuccess: () => {
      toast.success("User created");
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowNew(false);
    },
    onError: (e: any) => toast.error(getErrorMessage(e, "Failed")),
  });

  return (
    <div className="p-8 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <Shield className="h-6 w-6 text-brand-600" />
            Users & Roles
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Manage the people in your contract management system.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}>
          <Plus className="h-4 w-4" />
          Add user
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-xs uppercase">
            <tr>
              <th className="text-left px-5 py-3 font-semibold">Name</th>
              <th className="text-left px-5 py-3 font-semibold">Email</th>
              <th className="text-left px-5 py-3 font-semibold">Role</th>
              <th className="text-left px-5 py-3 font-semibold">Department</th>
              <th className="text-left px-5 py-3 font-semibold">Created</th>
              <th className="text-left px-5 py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(users ?? []).map((u: any) => (
              <tr key={u.id}>
                <td className="px-5 py-3 font-medium">{u.full_name}</td>
                <td className="px-5 py-3 text-slate-700">{u.email}</td>
                <td className="px-5 py-3">{roleLabel(u.role)}</td>
                <td className="px-5 py-3 text-slate-700">{u.department || "—"}</td>
                <td className="px-5 py-3 text-slate-500">{formatDateTime(u.created_at)}</td>
                <td className="px-5 py-3">
                  <span className={`badge ${u.is_active ? "bg-emerald-100 text-emerald-800 border-emerald-200" : "bg-slate-100 text-slate-700 border-slate-200"}`}>
                    {u.is_active ? "active" : "inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showNew && (
        <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center p-4 z-50">
          <div className="card w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">New user</h2>
            <div className="space-y-3">
              <div>
                <label className="label">Full name</label>
                <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              </div>
              <div>
                <label className="label">Email</label>
                <input className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Role</label>
                  <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                    {["admin", "executive", "legal", "finance", "compliance", "manager", "requester"].map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Department</label>
                  <input className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="label">Initial password</label>
                <input className="input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button className="btn btn-secondary" onClick={() => setShowNew(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={() => create.mutate(form)}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
