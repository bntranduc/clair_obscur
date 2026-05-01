"use client";

import { useEffect, useState } from "react";
import { Loader2, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import {
  fetchS3LogObjects,
  fetchS3LogSample,
  NORMALIZED_LOG_FIELDS_FALLBACK,
  type S3ObjectInfo,
} from "@/lib/api";

const PAGE_LINES = 50;

function cellDisplay(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function S3LogsPage() {
  const [objects, setObjects] = useState<S3ObjectInfo[]>([]);
  const [bucketInfo, setBucketInfo] = useState<{ bucket: string; prefix: string } | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [offsetLines, setOffsetLines] = useState(0);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [fieldOrder, setFieldOrder] = useState<string[]>(() => [...NORMALIZED_LOG_FIELDS_FALLBACK]);
  const [truncated, setTruncated] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoadingList(true);
        setError(null);
        const data = await fetchS3LogObjects(200);
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
  }, []);

  const loadSample = async (key: string, offset: number) => {
    if (!key) return;
    try {
      setLoadingRows(true);
      setError(null);
      const data = await fetchS3LogSample(key, { offsetLines: offset, limitLines: PAGE_LINES });
      setRows(data.logs);
      setFieldOrder(
        data.field_order?.length ? data.field_order : [...NORMALIZED_LOG_FIELDS_FALLBACK]
      );
      setTruncated(data.truncated);
      setOffsetLines(data.offset_lines);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    } finally {
      setLoadingRows(false);
    }
  };

  useEffect(() => {
    if (selectedKey) loadSample(selectedKey, 0);
  }, [selectedKey]);

  const colCount = fieldOrder.length || NORMALIZED_LOG_FIELDS_FALLBACK.length;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white mb-2">Logs S3</h1>
        <p className="text-gray-400 text-sm">
          Fichiers sous{" "}
          <code className="text-indigo-300">
            {bucketInfo ? `${bucketInfo.bucket}/${bucketInfo.prefix}` : "…"}
          </code>{" "}
          — échantillon JSONL gzip (extrait <code className="text-indigo-300">_source</code>, puis{" "}
          <code className="text-indigo-300">normalize()</code> : toutes les colonnes{" "}
          <code className="text-indigo-300">NormalizedEvent</code>).
        </p>
      </header>

      <div className="flex flex-wrap gap-4 items-end bg-white/5 p-4 rounded-xl border border-white/10">
        <div className="flex flex-col gap-1 min-w-[280px] flex-1">
          <label className="text-xs text-gray-500 uppercase tracking-wider">Objet S3</label>
          <select
            value={selectedKey}
            onChange={(e) => {
              setSelectedKey(e.target.value);
              setOffsetLines(0);
            }}
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
          onClick={() => selectedKey && loadSample(selectedKey, 0)}
          disabled={!selectedKey || loadingRows}
          className="flex items-center gap-2 px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-sm hover:bg-white/15 disabled:opacity-40"
        >
          <RefreshCw size={16} className={loadingRows ? "animate-spin" : ""} />
          Recharger depuis le début
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-200 text-sm">{error}</div>
      )}

      <div className="glass-panel border border-white/10 rounded-xl overflow-hidden">
        {loadingRows && rows.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-gray-500">
            <Loader2 size={24} className="animate-spin mr-3" /> Chargement des lignes…
          </div>
        ) : (
          <div className="overflow-x-auto">
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
                  <tr key={`${cellDisplay(row.timestamp)}-${i}`} className="hover:bg-white/5">
                    {fieldOrder.map((key) => (
                      <td
                        key={key}
                        className="p-3 font-mono text-xs text-gray-300 max-w-[14rem] truncate align-top"
                        title={cellDisplay(row[key])}
                      >
                        {cellDisplay(row[key])}
                      </td>
                    ))}
                  </tr>
                ))}
                {rows.length === 0 && !loadingRows && (
                  <tr>
                    <td colSpan={colCount} className="p-12 text-center text-gray-500">
                      Aucune ligne (fichier vide ou préfixe sans objets).
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex justify-between items-center text-sm text-gray-500">
        <button
          type="button"
          onClick={() => {
            const next = Math.max(0, offsetLines - PAGE_LINES);
            setOffsetLines(next);
            selectedKey && loadSample(selectedKey, next);
          }}
          disabled={offsetLines === 0 || loadingRows || !selectedKey}
          className="flex items-center gap-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-gray-400 hover:text-white disabled:opacity-30"
        >
          <ChevronLeft size={16} /> Lignes précédentes
        </button>
        <span>
          Offset lignes : {offsetLines} · {PAGE_LINES} lignes · {truncated ? "suite disponible →" : "fin fichier"}
        </span>
        <button
          type="button"
          onClick={() => {
            const next = offsetLines + PAGE_LINES;
            setOffsetLines(next);
            selectedKey && loadSample(selectedKey, next);
          }}
          disabled={!truncated || loadingRows || !selectedKey}
          className="flex items-center gap-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-gray-400 hover:text-white disabled:opacity-30"
        >
          Lignes suivantes <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
