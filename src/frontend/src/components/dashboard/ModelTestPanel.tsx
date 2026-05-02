"use client";

import { useCallback, useMemo, useState } from "react";
import { Loader2, Play, RotateCcw } from "lucide-react";
import { PredictAlertsCards } from "@/components/dashboard/PredictAlertsCards";
import { getModelPredictUrl } from "@/lib/modelPredict";
import { postPredict } from "@/lib/predictClient";

const DEFAULT_EVENTS_JSON = `[
  {"timestamp":"2026-01-15T08:00:01Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"root"},
  {"timestamp":"2026-01-15T08:00:02Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"admin"},
  {"timestamp":"2026-01-15T08:00:03Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"ubuntu"},
  {"timestamp":"2026-01-15T08:00:04Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"test"},
  {"timestamp":"2026-01-15T08:00:05Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"oracle"}
]`;

function parseEventsPayload(raw: string): { events: Record<string, unknown>[] } {
  const trimmed = raw.trim();
  if (!trimmed) throw new Error("Colle au moins un événement JSON.");
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("JSON invalide.");
  }
  if (Array.isArray(parsed)) {
    return { events: parsed as Record<string, unknown>[] };
  }
  if (parsed && typeof parsed === "object" && Array.isArray((parsed as { events?: unknown }).events)) {
    return { events: (parsed as { events: Record<string, unknown>[] }).events };
  }
  throw new Error('Format attendu : tableau [...] ou objet {"events":[...]}');
}

export function ModelTestPanel() {
  const [input, setInput] = useState(DEFAULT_EVENTS_JSON);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [responseRaw, setResponseRaw] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);

  const predictUrl = useMemo(() => getModelPredictUrl(), []);

  const run = useCallback(async () => {
    setErr(null);
    setResponseRaw(null);
    setAlerts([]);
    let body: { events: Record<string, unknown>[] };
    try {
      body = parseEventsPayload(input);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      return;
    }
    if (!body.events.length) {
      setErr("La liste events est vide.");
      return;
    }
    setLoading(true);
    try {
      const { alerts: nextAlerts, rawText } = await postPredict(body.events);
      setResponseRaw(rawText);
      setAlerts(nextAlerts);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [input, predictUrl]);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Tester le modèle</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Colle un tableau d’événements normalisés (ou <span className="font-mono text-zinc-400">{"{ \"events\": [...] }"}</span>
          ). Envoi vers <span className="font-mono text-indigo-300 text-xs">{predictUrl}</span>
          {process.env.NEXT_PUBLIC_MODEL_API_URL ? (
            <span className="text-zinc-600"> (URL publique)</span>
          ) : (
            <span className="text-zinc-600"> (via proxy Next → FRONTEND_MODEL_PROXY_TARGET)</span>
          )}
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <section className="rounded-2xl border border-white/[0.08] bg-zinc-900/40 overflow-hidden flex flex-col min-h-[320px]">
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-zinc-300">Entrée (events)</span>
            <button
              type="button"
              onClick={() => setInput(DEFAULT_EVENTS_JSON)}
              className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 px-2 py-1 rounded-md hover:bg-white/5"
            >
              <RotateCcw size={14} /> Exemple SSH
            </button>
          </div>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            spellCheck={false}
            className="flex-1 min-h-[280px] w-full bg-black/40 text-zinc-200 text-sm font-mono p-4 resize-y focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500/30"
            placeholder='[{"timestamp":"…","log_source":"authentication",…}, …]'
          />
          <div className="p-4 border-t border-white/[0.06]">
            <button
              type="button"
              disabled={loading}
              onClick={() => void run()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
              Exécuter /predict
            </button>
          </div>
        </section>

        <section className="rounded-2xl border border-white/[0.08] bg-zinc-900/40 overflow-hidden flex flex-col min-h-[320px]">
          <div className="px-4 py-3 border-b border-white/[0.06]">
            <span className="text-sm font-medium text-zinc-300">Réponse</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {err && (
              <div className="rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200 whitespace-pre-wrap">
                {err}
              </div>
            )}
            {!err && !responseRaw && !loading && (
              <p className="text-sm text-zinc-500">Lance une prédiction pour voir les alertes ici.</p>
            )}
            {loading && <p className="text-sm text-zinc-500 flex items-center gap-2">Appel au modèle…</p>}
            {alerts.length > 0 && <PredictAlertsCards alerts={alerts} />}
            {responseRaw && !loading && (
              <details className="group">
                <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">
                  JSON brut
                </summary>
                <pre className="mt-2 text-[11px] text-zinc-400 font-mono whitespace-pre-wrap break-words bg-black/50 rounded-lg p-3 border border-white/[0.06] max-h-64 overflow-auto">
                  {responseRaw}
                </pre>
              </details>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
