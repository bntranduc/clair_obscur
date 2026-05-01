"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import {
  fetchPredictionS3Objects,
  fetchPredictionsFile,
  type PredictionsApiPrefix,
  type S3ObjectInfo,
} from "@/lib/api";

const ALERT_FIELDS_FALLBACK = [
  "_id",
  "_index",
  "dataset",
  "challenge_id",
  "attack_type",
  "attacker_ips",
  "victim_accounts",
  "attack_window_start",
  "attack_window_end",
  "indicators",
  "sources_needed",
  "points_max",
];

function cellDisplay(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

type Props = {
  apiPrefix: PredictionsApiPrefix;
  title: string;
  bucketLabel: string;
};

export function PredictionsAlertsPage({ apiPrefix, title, bucketLabel }: Props) {
  const [objects, setObjects] = useState<S3ObjectInfo[]>([]);
  const [bucketInfo, setBucketInfo] = useState<{ bucket: string; prefix: string } | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [fieldOrder, setFieldOrder] = useState<string[]>(() => [...ALERT_FIELDS_FALLBACK]);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [alertCount, setAlertCount] = useState<number | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoadingList(true);
        setError(null);
        const data = await fetchPredictionS3Objects(apiPrefix, 200);
        if (cancelled) return;
        setBucketInfo({ bucket: data.bucket, prefix: data.prefix });
        setObjects(data.objects);
        if (data.objects.length && !selectedKey) {
          setSelectedKey(data.objects[0].key);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiPrefix]);

  const loadFile = useCallback(
    async (key: string) => {
      if (!key) return;
      try {
        setLoadingFile(true);
        setError(null);
        const data = await fetchPredictionsFile(apiPrefix, key);
        setRows(data.rows);
        setFieldOrder(data.field_order?.length ? data.field_order : [...ALERT_FIELDS_FALLBACK]);
        setMeta(data.meta ?? null);
        setAlertCount(data.alert_count);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setRows([]);
        setMeta(null);
        setAlertCount(null);
      } finally {
        setLoadingFile(false);
      }
    },
    [apiPrefix]
  );

  useEffect(() => {
    if (selectedKey) void loadFile(selectedKey);
  }, [selectedKey, loadFile]);

  const colCount = fieldOrder.length || ALERT_FIELDS_FALLBACK.length;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white mb-2">{title}</h1>
        <p className="text-gray-400 text-sm">
          Fichiers JSON de prédictions sous{" "}
          <code className="text-indigo-300">
            {bucketInfo ? `${bucketInfo.bucket}/${bucketInfo.prefix}` : bucketLabel}
          </code>{" "}
          — tableau des alertes renvoyées par le modèle (format DS1 /{" "}
          <code className="text-indigo-300">PredictResponse.alerts</code>).
        </p>
      </header>

      <div className="flex flex-wrap gap-4 items-end bg-white/5 p-4 rounded-xl border border-white/10">
        <div className="flex flex-col gap-1 min-w-[280px] flex-1">
          <label className="text-xs text-gray-500 uppercase tracking-wider">Objet S3</label>
          <select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            disabled={loadingList || objects.length === 0}
            className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
          >
            {objects.length === 0 ? (
              <option value="">—</option>
            ) : (
              objects.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.key.split("/").slice(-1)[0]} ({Math.round(o.size / 1024)} Ko)
                </option>
              ))
            )}
          </select>
        </div>
        <button
          type="button"
          onClick={() => selectedKey && loadFile(selectedKey)}
          disabled={!selectedKey || loadingFile}
          className="flex items-center gap-2 px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-sm hover:bg-white/15 disabled:opacity-40"
        >
          <RefreshCw size={16} className={loadingFile ? "animate-spin" : ""} />
          Recharger le fichier
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-200 text-sm">{error}</div>
      )}

      {meta && Object.keys(meta).length > 0 && (
        <details className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-gray-400">
          <summary className="cursor-pointer text-gray-300 font-medium">Métadonnées fichier (meta)</summary>
          <pre className="mt-3 text-xs font-mono text-indigo-200/90 whitespace-pre-wrap overflow-x-auto">
            {JSON.stringify(meta, null, 2)}
          </pre>
        </details>
      )}

      <div className="glass-panel border border-white/10 rounded-xl overflow-hidden">
        {loadingFile && rows.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-gray-500">
            <Loader2 size={24} className="animate-spin mr-3" /> Chargement des alertes…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="px-4 py-2 text-xs text-gray-500 border-b border-white/10">
              {alertCount !== null ? `${alertCount} alerte${alertCount === 1 ? "" : "s"}` : ""}
            </div>
            <table className="w-full text-left border-collapse text-sm min-w-max">
              <thead>
                <tr className="border-b border-white/10 text-gray-400 text-xs uppercase tracking-wider bg-black/20">
                  {fieldOrder.map((key) => (
                    <th key={key} className="p-3 font-medium whitespace-nowrap">
                      {key.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {rows.map((row, i) => (
                  <tr key={`${cellDisplay(row._id)}-${i}`} className="hover:bg-white/5">
                    {fieldOrder.map((key) => (
                      <td
                        key={key}
                        className="p-3 font-mono text-xs text-gray-300 max-w-[16rem] truncate align-top"
                        title={cellDisplay(row[key])}
                      >
                        {cellDisplay(row[key])}
                      </td>
                    ))}
                  </tr>
                ))}
                {rows.length === 0 && !loadingFile && (
                  <tr>
                    <td colSpan={colCount} className="p-12 text-center text-gray-500">
                      Aucune alerte dans ce fichier (ou fichier vide / liste d&apos;objets vide).
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
