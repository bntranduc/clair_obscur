"use client";

import { useCallback, useState } from "react";
import { Loader2, Cpu, Upload } from "lucide-react";
import { callModelPredict } from "@/lib/api";

/**
 * Accepte :
 * - ``{ "events": [ ... ] }``
 * - un tableau d'événements normalisés
 * - un tableau de hits OpenSearch ``{ "_source": { ... } }``
 */
function parseEventsFromJsonText(raw: string): Record<string, unknown>[] {
  const trimmed = raw.trim();
  if (!trimmed) throw new Error("JSON vide.");
  const data: unknown = JSON.parse(trimmed);
  if (Array.isArray(data)) {
    if (
      data.length > 0 &&
      typeof data[0] === "object" &&
      data[0] !== null &&
      "_source" in (data[0] as object)
    ) {
      return (data as { _source: Record<string, unknown> }[]).map((h) => h._source);
    }
    return data as Record<string, unknown>[];
  }
  if (typeof data === "object" && data !== null && "events" in data) {
    const ev = (data as { events: unknown }).events;
    if (!Array.isArray(ev)) throw new Error('Clé "events" : attendu un tableau.');
    return ev as Record<string, unknown>[];
  }
  throw new Error(
    "Format non reconnu : tableau d’événements, ou { \"events\": [...] }, ou tableau de hits avec _source."
  );
}

export default function CallModelPage() {
  const [jsonInput, setJsonInput] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      setJsonInput(typeof reader.result === "string" ? reader.result : "");
      setError(null);
      setResult(null);
    };
    reader.readAsText(f);
    e.target.value = "";
  }, []);

  const run = async () => {
    try {
      setLoading(true);
      setError(null);
      setResult(null);
      const events = parseEventsFromJsonText(jsonInput);
      const out = await callModelPredict(events);
      setResult(JSON.stringify(out, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Cpu className="text-indigo-400" size={28} />
        <div>
          <h1 className="text-2xl font-bold">Appeler le modèle</h1>
          <p className="text-gray-400 text-sm mt-1 max-w-2xl">
            Colle ou importe un JSON : liste d’événements normalisés, ou{" "}
            <code className="text-indigo-300">{"{ \"events\": [...] }"}</code>, ou export OpenSearch (tableau de hits
            avec <code className="text-indigo-300">_source</code>). Envoi vers{" "}
            <code className="text-indigo-300">POST /api/v1/model/predict</code> sur l’API dashboard.
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-950/40 px-4 py-3 text-red-200 text-sm whitespace-pre-wrap">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3 items-center">
        <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 cursor-pointer text-sm border border-white/10">
          <Upload size={16} />
          Importer un fichier JSON
          <input type="file" accept=".json,application/json" className="hidden" onChange={onFile} />
        </label>
        <button
          type="button"
          onClick={() => {
            setJsonInput("");
            setResult(null);
            setError(null);
          }}
          className="px-4 py-2 rounded-lg text-sm border border-white/10 text-gray-300 hover:bg-white/5"
        >
          Effacer
        </button>
        <button
          type="button"
          onClick={run}
          disabled={loading || !jsonInput.trim()}
          className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:pointer-events-none text-sm font-medium"
        >
          {loading ? <Loader2 className="animate-spin" size={18} /> : null}
          Lancer la prédiction
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Entrée JSON</label>
          <textarea
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            spellCheck={false}
            placeholder='[{"timestamp":"2026-01-01T12:00:00Z","source_ip":"10.0.0.1",...}]'
            className="w-full min-h-[320px] rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-xs text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Réponse (alertes)</label>
          <pre className="w-full min-h-[320px] max-h-[70vh] overflow-auto rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-xs text-emerald-200/90 whitespace-pre-wrap">
            {result ?? "—"}
          </pre>
        </div>
      </div>
    </div>
  );
}
