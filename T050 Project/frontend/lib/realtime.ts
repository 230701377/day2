"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createClient, SupabaseClient } from "@supabase/supabase-js";

export interface ApprovalStep {
  id: string;
  step_index: number;
  step_name: string;
  required_role: string;
  decision: "not_started" | "pending" | "approved" | "rejected" | "changes_requested" | "skipped" | string;
  sla_hours?: number;
  due_at?: string;
  decided_at?: string | null;
}

export interface ContractItem {
  id: string;
  title: string;
  contract_number: string;
  contract_type: string;
  status: string;
  counterparty?: string | null;
  owner_id: string;
  department?: string | null;
  value_amount?: number | null;
  value_currency?: string;
  effective_date?: string | null;
  expiration_date?: string | null;
  auto_renew?: boolean;
  renewal_notice_days?: number;
  risk_score?: number;
  risk_level?: string;
  processing_status?: string;
  processing_step?: string | null;
  processing_progress?: number;
  ai_confidence?: string;
  approval_steps?: ApprovalStep[];
  current_approval_step?: string | null;
  created_at?: string;
  updated_at?: string;
  [key: string]: any;
}

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://hfqprgbcwtqtceqazsse.supabase.co";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let supabaseInstance: SupabaseClient | null = null;
if (SUPABASE_URL && SUPABASE_ANON_KEY) {
  try {
    supabaseInstance = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  } catch (err) {
    console.warn("Failed to initialize Supabase client:", err);
  }
}

export function getSupabaseClient(): SupabaseClient | null {
  return supabaseInstance;
}

interface UseRealtimeContractsOptions {
  onEvent?: (event: string, payload: any) => void;
}

/**
 * Resilient Real-Time Hook for Contracts
 * Synchronizes with Supabase Realtime (postgres_changes on contracts, approvals, workflows)
 * and Backend WebSockets (/ws/contracts & /ws/notifications) with in-place deduplication.
 */
export function useRealtimeContracts(
  initialContracts: ContractItem[] = [],
  options?: UseRealtimeContractsOptions
) {
  const qc = useQueryClient();
  const [contracts, setContracts] = useState<ContractItem[]>(initialContracts);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef<boolean>(true);
  
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const qcRef = useRef(qc);
  qcRef.current = qc;

  // Sync initial contracts if loaded from query without infinite loop
  const initialHashRef = useRef<string>("");
  useEffect(() => {
    if (initialContracts && Array.isArray(initialContracts) && initialContracts.length > 0) {
      const hash = initialContracts.map((c) => c.id).join(",");
      if (hash === initialHashRef.current) return;
      initialHashRef.current = hash;

      setContracts((prev) => {
        const map = new Map<string, ContractItem>();
        initialContracts.forEach((c) => {
          if (c && c.id) map.set(c.id, c);
        });

        prev.forEach((p) => {
          if (p && p.id && map.has(p.id)) {
            map.set(p.id, { ...map.get(p.id)!, ...p });
          }
        });

        return Array.from(map.values());
      });
    }
  }, [initialContracts]);

  // Handle in-place INSERT
  const handleInsert = useCallback((newContract: ContractItem) => {
    if (!newContract || !newContract.id) return;
    setContracts((prev) => {
      const index = prev.findIndex((c) => c.id === newContract.id);
      if (index >= 0) {
        const updated = [...prev];
        updated[index] = { ...updated[index], ...newContract };
        return updated;
      }
      return [newContract, ...prev];
    });
    qcRef.current.invalidateQueries({ queryKey: ["analytics-overview"] });
    qcRef.current.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qcRef.current.invalidateQueries({ queryKey: ["renewals"] });
    qcRef.current.invalidateQueries({ queryKey: ["renewals-60"] });
    optionsRef.current?.onEvent?.("INSERT", newContract);
  }, []);

  // Handle in-place UPDATE
  const handleUpdate = useCallback((updatedContract: Partial<ContractItem> & { id: string }) => {
    if (!updatedContract || !updatedContract.id) return;
    setContracts((prev) => {
      const index = prev.findIndex((c) => c.id === updatedContract.id);
      if (index >= 0) {
        const updated = [...prev];
        updated[index] = { ...updated[index], ...updatedContract };
        return updated;
      }
      return prev;
    });
    qcRef.current.invalidateQueries({ queryKey: ["analytics-overview"] });
    qcRef.current.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qcRef.current.invalidateQueries({ queryKey: ["renewals"] });
    qcRef.current.invalidateQueries({ queryKey: ["renewals-60"] });
    optionsRef.current?.onEvent?.("UPDATE", updatedContract);
  }, []);

  // Handle in-place DELETE
  const handleDelete = useCallback((contractId: string) => {
    if (!contractId) return;
    setContracts((prev) => prev.filter((c) => c.id !== contractId));
    qcRef.current.invalidateQueries({ queryKey: ["analytics-overview"] });
    qcRef.current.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qcRef.current.invalidateQueries({ queryKey: ["renewals"] });
    qcRef.current.invalidateQueries({ queryKey: ["renewals-60"] });
    optionsRef.current?.onEvent?.("DELETE", { id: contractId });
  }, []);

  // Handle Approval Step Updates
  const handleApprovalUpdate = useCallback((payload: any) => {
    const contractId = payload.contract_id || payload.contract?.id;
    if (!contractId) return;

    if (payload.contract) {
      handleUpdate(payload.contract);
      return;
    }

    setContracts((prev) => {
      const index = prev.findIndex((c) => c.id === contractId);
      if (index < 0) return prev;

      const currentContract = prev[index];
      const existingSteps = currentContract.approval_steps ? [...currentContract.approval_steps] : [];

      if (payload.approval_id || payload.step_name) {
        const stepIdx = existingSteps.findIndex(
          (s) => s.id === payload.approval_id || s.step_name === payload.step_name
        );
        if (stepIdx >= 0) {
          existingSteps[stepIdx] = {
            ...existingSteps[stepIdx],
            decision: payload.decision || existingSteps[stepIdx].decision,
          };
        }
      }

      const updated = [...prev];
      updated[index] = {
        ...currentContract,
        approval_steps: existingSteps,
        status: payload.status || currentContract.status,
        current_approval_step: payload.current_step || currentContract.current_approval_step,
      };
      return updated;
    });

    qcRef.current.invalidateQueries({ queryKey: ["analytics-overview"] });
    qcRef.current.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qcRef.current.invalidateQueries({ queryKey: ["approvals"] });
    qcRef.current.invalidateQueries({ queryKey: ["approvals-inbox"] });
    qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
    qcRef.current.invalidateQueries({ queryKey: ["contract-approvals-timeline"] });
    optionsRef.current?.onEvent?.("APPROVAL_UPDATE", payload);
  }, [handleUpdate]);

  // 1. Supabase Realtime Setup
  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) return;

    const channel = supabase
      .channel("clm-realtime-contracts")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "contracts" },
        (payload) => {
          handleInsert(payload.new as ContractItem);
        }
      )
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "contracts" },
        (payload) => {
          handleUpdate(payload.new as ContractItem);
        }
      )
      .on(
        "postgres_changes",
        { event: "DELETE", schema: "public", table: "contracts" },
        (payload) => {
          if (payload.old && payload.old.id) {
            handleDelete(payload.old.id);
          }
        }
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "approvals" },
        (payload) => {
          const newApproval: any = payload.new;
          if (newApproval && newApproval.contract_id) {
            handleApprovalUpdate({
              contract_id: newApproval.contract_id,
              approval_id: newApproval.id,
              step_name: newApproval.step_name,
              decision: newApproval.decision,
            });
          }
        }
      )
      .subscribe((status) => {
        if (status === "SUBSCRIBED") {
          setIsConnected(true);
        } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT" || status === "CLOSED") {
          setIsConnected(false);
          qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
        }
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [handleInsert, handleUpdate, handleDelete, handleApprovalUpdate]);

  // 2. Backend WebSocket Setup (contracts channel)
  useEffect(() => {
    isMountedRef.current = true;

    const connectWebSocket = () => {
      if (!isMountedRef.current) return;

      const wsProtocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = typeof window !== "undefined" && window.location.hostname ? window.location.hostname : "localhost";
      const wsUrl = `${wsProtocol}//${host}:8000/api/v1/ws/contracts`;

      try {
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          if (!isMountedRef.current) return;
          setIsConnected(true);
          qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
        };

        socket.onmessage = (event) => {
          if (!isMountedRef.current) return;
          try {
            const data = JSON.parse(event.data);
            if (data.event === "connected" || data.event === "pong") return;

            if (data.event === "contract_inserted" && data.data) {
              handleInsert(data.data);
              qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
              qcRef.current.invalidateQueries({ queryKey: ["dashboard-summary"] });
            } else if (data.event === "contract_updated" && data.data) {
              handleUpdate(data.data);
              qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
              qcRef.current.invalidateQueries({ queryKey: ["approvals-inbox"] });
              qcRef.current.invalidateQueries({ queryKey: ["contract-approvals-timeline"] });
            } else if (data.event === "contract_deleted" && (data.data?.id || data.contract_id)) {
              handleDelete(data.data?.id || data.contract_id);
              qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
              qcRef.current.invalidateQueries({ queryKey: ["approvals-inbox"] });
            } else if (data.event === "approval_updated") {
              handleApprovalUpdate(data);
              qcRef.current.invalidateQueries({ queryKey: ["contracts"] });
              qcRef.current.invalidateQueries({ queryKey: ["approvals-inbox"] });
              qcRef.current.invalidateQueries({ queryKey: ["contract-approvals-timeline"] });
            }
          } catch (parseErr) {
            console.warn("Realtime WebSocket parse error:", parseErr);
          }
        };

        socket.onclose = () => {
          if (!isMountedRef.current) return;
          setIsConnected(false);
          reconnectTimeoutRef.current = setTimeout(connectWebSocket, 4000);
        };

        socket.onerror = () => {
          try {
            socket.close();
          } catch (_) {}
        };
      } catch (err) {
        console.warn("Realtime WebSocket connection failed:", err);
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 4000);
      }
    };

    connectWebSocket();

    const pingInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);

    return () => {
      isMountedRef.current = false;
      clearInterval(pingInterval);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (_) {}
      }
    };
  }, [handleInsert, handleUpdate, handleDelete, handleApprovalUpdate]);

  return {
    contracts,
    setContracts,
    isConnected,
    handleInsert,
    handleUpdate,
    handleDelete,
    handleApprovalUpdate,
  };
}
