"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, fetchMe } from "@/lib/api";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { accessToken, user, setSession, logout } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (pathname === "/login") return;

    const token = accessToken || (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

    if (!token) {
      router.replace("/login");
      return;
    }

    if (!user) {
      fetchMe()
        .then((u) => setSession(u, token, useAuth.getState().refreshToken || ""))
        .catch((err) => {
          console.warn("fetchMe error:", err);
          if (err?.response?.status === 401) {
            logout();
            router.replace("/login");
          }
        });
    }
  }, [mounted, accessToken, user, pathname, router, setSession, logout]);

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  const hasToken = accessToken || (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

  if (!hasToken && pathname !== "/login") {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  return <>{children}</>;
}
