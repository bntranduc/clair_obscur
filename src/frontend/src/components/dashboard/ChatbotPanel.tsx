"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { postChat, type ChatMessage } from "@/lib/api";

export function ChatbotPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setErr(null);
    const nextUser: ChatMessage = { role: "user", content: text };
    const history = [...messages, nextUser];
    setMessages(history);
    setInput("");
    setLoading(true);
    try {
      const { reply } = await postChat(history);
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages((prev) => prev.slice(0, -1));
      setErr(e instanceof Error ? e.message : String(e));
      setInput(text);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages]);

  return (
    <div className="space-y-6 max-w-3xl flex flex-col min-h-[calc(100vh-10rem)]">
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Assistant Clair Obscur</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Même moteur Bedrock que le script{' '}
          <span className="font-mono text-zinc-400 text-xs">simple_prompt.py</span> — contexte SOC, logs S3,
          détection. API{' '}
          <span className="font-mono text-zinc-400 text-xs">POST /api/v1/chat</span>.
        </p>
      </div>

      <div className="flex-1 flex flex-col rounded-2xl border border-white/[0.08] bg-zinc-900/40 overflow-hidden min-h-[420px]">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !loading && (
            <p className="text-sm text-zinc-500 text-center py-12 max-w-md mx-auto leading-relaxed">
              Exemple : « Comment interpréter une série d’échecs SSH depuis la même IP ? » ou « À quoi sert la
              normalisation des logs avant détection ? »
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={`${i}-${m.role}`}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-indigo-600/90 text-white"
                    : "bg-black/45 text-zinc-200 border border-white/[0.06]"
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-3 bg-black/45 border border-white/[0.06] flex items-center gap-2 text-zinc-400 text-sm">
                <Loader2 size={16} className="animate-spin" />
                Réponse…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {err && (
          <div className="mx-4 mb-2 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200 whitespace-pre-wrap">
            {err}
          </div>
        )}

        <div className="p-4 border-t border-white/[0.06] flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            disabled={loading}
            rows={2}
            placeholder="Question sur logs, alertes ou SOC… (Entrée envoyer)"
            className="flex-1 resize-none rounded-xl bg-black/40 border border-white/[0.08] text-zinc-100 text-sm px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 placeholder:text-zinc-600"
          />
          <button
            type="button"
            disabled={loading || !input.trim()}
            onClick={() => void send()}
            className="shrink-0 self-end inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
