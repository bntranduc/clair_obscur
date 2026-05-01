"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import {
  fetchPredictionFile,
  fetchPredictionObjects,
  type AlertsPool,
  type S3ObjectInfo,
} from "@/lib/api";

const ALERT_COLUMNS = [
  "_id",
  "challenge_id",
  "attack_type",
  "attacker_ips",
  "victim_accounts",
  "window_start",
  "window_end",
  "points_max",
  "sources_needed",
  "indicators",
] as const;

function cellDisplay(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function flattenAlertHit(hit: unknown): Record<string, unknown> {
  if (!hit || typeof hit !== "object") {
    return { _id: "—" };
  }
  const h = hit as Record<string, unknown>;
  const src = (h._source as Record<string, unknown>) || {};
  const win = (src.attack_window as Record<string, unknown>) || {};
  return {
    _id: h._id,
    challenge_id: src.challenge_id,
    attack_type: src.attack_type,
    attacker_ips: src.attacker_ips,
    victim_accounts: src.victim_accounts,
    window_start: win.start,
    window_end: win.end,
    points_max: src.points_max,
    sources_needed: src.sources_needed,
    indicators: src.indicators,
  };
}

type Props = {
  pool: AlertsPool;
  title: string;
  bucketLabel: string;
};

export function AlertsPoolView({ pool, title, bucketLabel }: Props) {
  const [objects, setObjects] = useState<S3ObjectInfo[]>([]);
  const [bucketInfo, setBucketInfo] = useState<{ bucket: string; prefix: string } | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoadingList(true);
        setError(null);
        const data = await fetchPredictionObjects(pool, 200);
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
  }, [pool]);

  const loadFile = useCallback(
    async (key: string) => {
      if (!key) return;
      try {
        setLoadingFile(true);
        setError(null);
        const data = await fetchPredictionFile(pool, key);
        setRows(data.alerts.map(flattenAlertHit));
        setMeta(data.meta);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setRows([]);
        setMeta(null);
      } finally {
        setLoadingFile(false);
      }
    },
    [pool]
  );

  useEffect(() => {
    if (selectedKey) void loadFile(selectedKey);
  }, [selectedKey, loadFile]);

  const colCount = ALERT_COLUMNS.length;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white mb-2">{title}</h1>
        <p className="text-gray-400 text-sm">
          Fichiers JSON de prédictions sous{" "}
          <code className="text-indigo-300">
            {bucketLabel} — {bucketInfo ? `${bucketInfo.bucket}/${bucketInfo.prefix}` : "…"}
          </code>
          . Chaque fichier contient un tableau <code className="text-indigo-300">alerts</code> (format type
          ground truth DS1).
        </p>
      </header>

      <div className="flex flex-wrap gap-4 items-end bg-white/5 p-4 rounded-xl border border-white/10">
        <div className="flex flex-col gap-1 min-w-[280px] flex-1">
          <label className="text-xs text-gray-500 uppercase tracking-wider">Fichier S3</label>
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
                  {o.key.split("/").slice(-2).join("/")} ({Math.round(o.size / 1024)} Ko)
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
          Recharger
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-200 text-sm">{error}</div>
      )}

      {meta && Object.keys(meta).length > 0 && (
        <div className="text-xs text-gray-500 font-mono bg-black/30 border border-white/5 rounded-lg p-3 overflow-x-auto">
          <span className="text-gray-400">meta</span> {cellDisplay(meta)}
        </div>
      )}

      <div className="glass-panel border border-white/10 rounded-xl overflow-hidden">
        {loadingFile && rows.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-gray-500">
            <Loader2 size={24} className="animate-spin mr-3" /> Chargement des alertes…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm min-w-max">
              <thead>
                <tr className="border-b border-white/10 text-gray-400 text-xs uppercase tracking-wider bg-black/20">
                  {ALERT_COLUMNS.map((key) => (
                    <th key={key} className="p-3 font-medium whitespace-nowrap">
                      {key.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {rows.map((row, i) => (
                  <tr key={`${cellDisplay(row._id)}-${i}`} className="hover:bg-white/5">
                    {ALERT_COLUMNS.map((key) => (
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
                      Aucune alerte dans ce fichier (ou fichier vide / non listé).
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
