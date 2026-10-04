"use client";

import { useState, useEffect } from "react";
import { Bell, CheckCircle2, AlertTriangle, Info, X } from "lucide-react";
import toast from "react-hot-toast";

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: "info" | "warning" | "success";
  timestamp: string;
}

export default function NotificationCenter() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    // Construct WebSocket URL matching current location host
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "localhost";
    const wsUrl = `${wsProtocol}//${host}:8000/api/v1/ws/notifications`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "connected" || data.event === "pong") return;

          const newItem: NotificationItem = {
            id: Math.random().toString(36).substring(7),
            title: data.title || data.event?.replace(/_/g, " ").toUpperCase() || "System Notification",
            message: data.message || `Activity on contract ${data.contract_id || ""}`,
            type: data.severity === "WARNING" ? "warning" : "info",
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          };

          setNotifications((prev) => [newItem, ...prev.slice(0, 19)]);
          setUnreadCount((prev) => prev + 1);

          // Trigger live toast
          if (data.severity === "WARNING") {
            toast.error(newItem.title, { duration: 4000 });
          } else {
            toast.success(newItem.title, { duration: 3000 });
          }
        } catch (e) {
          console.warn("WebSocket parse error:", e);
        }
      };
    } catch (err) {
      console.warn("WebSocket connection error:", err);
    }

    return () => {
      if (socket) socket.close();
    };
  }, []);

  return (
    <div className="relative">
      <button
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) setUnreadCount(0);
        }}
        className="relative p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
        title="Live Notifications"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 h-4 w-4 bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-brand-600" />
              <span className="font-bold text-sm text-slate-900">Notifications</span>
              <span className="badge badge-brand text-[10px]">{notifications.length}</span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-slate-600">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
            {notifications.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-xs">
                No active notifications. Live WebSocket hub listening...
              </div>
            ) : (
              notifications.map((item) => (
                <div key={item.id} className="p-3.5 hover:bg-slate-50 transition-colors flex gap-3">
                  <div className="shrink-0 mt-0.5">
                    {item.type === "warning" ? (
                      <AlertTriangle className="h-4 w-4 text-rose-500" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold text-slate-900 truncate">{item.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5 leading-relaxed">{item.message}</div>
                    <div className="text-[10px] text-slate-400 mt-1">{item.timestamp}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
