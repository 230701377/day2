"use client";

import Sidebar from "./Sidebar";
import RequireAuth from "./RequireAuth";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="min-h-screen flex bg-slate-50">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-x-hidden">
          {children}
        </main>
      </div>
    </RequireAuth>
  );
}
