"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard, FileText, CheckSquare, AlertCircle, Calendar,
  History, Users, Settings, Search, LogOut, Shield, BarChart3,
} from "lucide-react";
import { useAuth } from "@/lib/api";
import { cn, roleLabel } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/contracts", label: "Contracts", icon: FileText },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/obligations", label: "Obligations", icon: AlertCircle },
  { href: "/renewals", label: "Renewals", icon: Calendar },
  { href: "/qa", label: "AI Q&A", icon: Search },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/audit", label: "Audit Trail", icon: History, roles: ["admin", "legal", "compliance", "executive", "manager"] },
  { href: "/admin/users", label: "Users", icon: Users, roles: ["admin"] },
];

import NotificationCenter from "./NotificationCenter";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const items = NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role)));

  return (
    <aside className="w-64 shrink-0 bg-white border-r border-slate-200 flex flex-col">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-brand-600 text-white flex items-center justify-center">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <div className="font-semibold text-slate-900 leading-tight">CLM</div>
            <div className="text-xs text-slate-500">Contract Platform</div>
          </div>
        </Link>
        <NotificationCenter />
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium",
                active ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-4 border-t border-slate-200">
        <div className="px-3 py-2 mb-2">
          <div className="text-sm font-medium text-slate-900 truncate">{user?.full_name}</div>
          <div className="text-xs text-slate-500 truncate">
            {user ? roleLabel(user.role) : ""}{user?.department ? ` · ${user.department}` : ""}
          </div>
        </div>
        <button
          onClick={() => { logout(); router.push("/login"); }}
          className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-slate-600 hover:bg-slate-100 w-full"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
