"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { login, useAuth, getErrorMessage } from "@/lib/api";
import { Shield } from "lucide-react";

const DEMO_USERS = [
  { email: "admin@acme.io", role: "Administrator" },
  { email: "exec@acme.io", role: "Executive" },
  { email: "legal@acme.io", role: "Legal" },
  { email: "finance@acme.io", role: "Finance" },
  { email: "compliance@acme.io", role: "Compliance" },
  { email: "manager@acme.io", role: "Manager" },
  { email: "requester@acme.io", role: "Requester" },
];

export default function LoginPage() {
  const [email, setEmail] = useState("admin@acme.io");
  const [password, setPassword] = useState("Demo1234!");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const { setSession } = useAuth();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await login(email, password);
      setSession(data.user, data.access_token, data.refresh_token);
      toast.success(`Welcome, ${data.user.full_name}`);
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(getErrorMessage(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  function pickDemo(em: string) {
    setEmail(em);
    setPassword("Demo1234!");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-brand-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white mb-3">
            <Shield className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Contract Lifecycle & Approval</h1>
          <p className="text-slate-500 text-sm mt-1">Enterprise CLM with AI contract intelligence</p>
        </div>
        <div className="card p-6">
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password" className="input" value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <button className="btn btn-primary w-full justify-center" disabled={busy}>
              {busy ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
        <div className="card p-4 mt-4">
          <div className="section-title mb-2">Demo accounts (password: Demo1234!)</div>
          <div className="grid grid-cols-2 gap-2">
            {DEMO_USERS.map((u) => (
              <button
                key={u.email}
                onClick={() => pickDemo(u.email)}
                className="text-left text-xs px-3 py-2 rounded-md border border-slate-200 hover:bg-slate-50"
              >
                <div className="font-medium text-slate-800">{u.role}</div>
                <div className="text-slate-500 truncate">{u.email}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
