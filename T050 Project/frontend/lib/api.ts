"use client";

import axios from "axios";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const apiBaseUrl = API_BASE;
const API = `${API_BASE}/api/v1`;

export const api = axios.create({
  baseURL: API,
});

api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  setSession: (user: User, access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setSession: (user, access, refresh) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("access_token", access);
          localStorage.setItem("refresh_token", refresh);
        }
        set({ user, accessToken: access, refreshToken: refresh });
      },
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        }
        set({ user: null, accessToken: null, refreshToken: null });
      },
    }),
    { name: "contracts-auth" }
  )
);

export async function login(email: string, password: string) {
  const r = await axios.post(`${API}/auth/login`, { email, password });
  return r.data as { access_token: string; refresh_token: string; user: User };
}

export async function fetchMe() {
  const r = await api.get("/auth/me");
  return r.data as User;
}

export function getErrorMessage(error: any, fallback = "An unexpected error occurred"): string {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  
  const data = error?.response?.data;
  if (data) {
    if (typeof data === "string") return data;
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail && typeof data.detail === "object") {
      if (typeof data.detail.message === "string") return data.detail.message;
      if (typeof data.detail.error === "string") return data.detail.error;
      try {
        return JSON.stringify(data.detail);
      } catch {
        // ignore
      }
    }
    if (typeof data?.message === "string") return data.message;
    if (typeof data?.error === "string") return data.error;
  }
  
  if (typeof error?.message === "string") return error.message;
  
  try {
    return JSON.stringify(error);
  } catch {
    return fallback;
  }
}
