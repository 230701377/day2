"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Search, Shield, FileText } from "lucide-react";

export default function QAPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState<"all" | "mine">("mine");

  async function ask() {
    if (!question.trim()) return;
    setBusy(true);
    setAnswer({ answer: "", confidence: 0, sources: [] });

    try {
      const token = localStorage.getItem("access_token") || localStorage.getItem("token");
      const res = await fetch("/api/proxy/qa/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ question, top_k: 5 }),
      });

      if (!res.body) {
        setBusy(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedAnswer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const rawData = line.slice(6).trim();
            if (!rawData) continue;
            try {
              const parsed = JSON.parse(rawData);
              if (parsed.sources) {
                setAnswer((prev: any) => ({
                  ...prev,
                  sources: parsed.sources,
                  confidence: parsed.confidence ?? 0.95
                }));
              } else if (parsed.citations) {
                setAnswer((prev: any) => ({
                  ...prev,
                  sources: parsed.citations,
                  confidence: 0.95
                }));
              } else if (parsed.token !== undefined) {
                accumulatedAnswer += parsed.token;
                setAnswer((prev: any) => ({
                  ...prev,
                  answer: accumulatedAnswer
                }));
              }
            } catch {
              accumulatedAnswer += rawData;
              setAnswer((prev: any) => ({
                ...prev,
                answer: accumulatedAnswer
              }));
            }
          }
        }
      }
    } catch (e) {
      console.warn("SSE stream error:", e);
    } finally {
      setBusy(false);
    }
  }

  const SUGGESTIONS = [
    "Which contracts auto-renew and what is the notice period?",
    "What contracts have unlimited liability?",
    "Show me contracts with GDPR obligations.",
    "What is the highest-value contract expiring soon?",
  ];

  return (
    <div className="p-8 max-w-screen-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">AI Q&A</h1>
        <p className="text-slate-500 text-sm mt-1">
          RAG-powered contract question answering. Answers are grounded in your authorized contracts
          with clause-level citations. No information leaves your contract repository.
        </p>
      </div>

      <div className="card p-5 mb-4">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Ask a question about your contracts..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
            />
          </div>
          <button className="btn btn-primary" onClick={ask} disabled={busy}>
            {busy ? "Thinking..." : "Ask"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <span className="text-xs text-slate-500">Try:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="text-xs px-2 py-1 rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
              onClick={() => { setQuestion(s); }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {answer && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="h-4 w-4 text-brand-600" />
            <div className="section-title">Grounded answer</div>
            <span className="text-xs text-slate-500 ml-auto">
              Confidence {(answer.confidence * 100).toFixed(1)}%
            </span>
          </div>
          <div className="text-slate-900 whitespace-pre-wrap leading-relaxed">{answer.answer}</div>

          {answer.sources?.length > 0 && (
            <div className="mt-5">
              <div className="section-title mb-2">Cited sources ({answer.sources.length})</div>
              <div className="space-y-2">
                {answer.sources.map((s: any, i: number) => (
                  <div key={i} className="border border-slate-200 rounded-md p-3">
                    <div className="flex items-center justify-between mb-1">
                      <div className="text-xs text-slate-700 font-medium flex items-center gap-1">
                        <FileText className="h-3 w-3" />
                        {s.contract_title}
                      </div>
                      <div className="text-xs text-slate-500">
                        relevance {(s.score * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="text-xs text-slate-500 mb-1">
                      Clause {s.heading || s.clause_id?.slice(0, 8)} · page {s.page_number ?? "?"}
                    </div>
                    <div className="text-sm text-slate-700 italic">"{s.excerpt}"</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
