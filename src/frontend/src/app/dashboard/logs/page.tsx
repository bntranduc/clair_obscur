"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Table2 } from "lucide-react";
import { fetchNormalizedLogs } from "@/lib/api";
import {
  NORMALIZED_TABLE_COLUMNS,
  formatCell,
  getByPath,
  type NormalizedEvent,
} from "@/lib/normalizedLog";

const PAGE_SIZE = 50;

export default function NormalizedLogsPage() {
  const [rows, setRows] = useState<NormalizedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchNormalizedLogs({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setRows(data.items);
      setHasMore(data.has_more);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement");
      setRows([]);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  const rangeStart = page * PAGE_SIZE + (rows.length ? 1 : 0);
  const rangeEnd = page * PAGE_SIZE + rows.length;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2 text-blue-400/90">
            <Table2 size={18} strokeWidth={2} className="shrink-0" aria-hidden />
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em]">Données S3</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Logs normalisés</h1>
          <p className="max-w-2xl text-[15px] leading-relaxed text-zinc-400">
            Schéma aligné sur <code className="rounded-md bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[13px] text-blue-300/90">NormalizedEvent</code> — défilement horizontal pour parcourir toutes les colonnes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-zinc-900/60 px-4 py-2 text-[13px] text-zinc-400">
            <span className="text-zinc-500">Lignes</span>
            <span className="font-medium tabular-nums text-zinc-200">
              {rows.length === 0 ? "0" : `${rangeStart}–${rangeEnd}`}
            </span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-500">{PAGE_SIZE} / page</span>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="focus-ring inline-flex items-center gap-2 rounded-xl bg-blue-500/15 px-4 py-2.5 text-sm font-medium text-blue-100 ring-1 ring-blue-400/25 transition hover:bg-blue-500/25 disabled:opacity-60"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden />
            Actualiser
          </button>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-red-500/25 bg-red-950/40 px-4 py-3 text-sm text-red-200 ring-1 ring-red-500/20"
        >
          {error}
        </div>
      )}

      <div className="panel overflow-hidden">
        {loading && rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-24 text-zinc-500">
            <Loader2 size={28} className="animate-spin text-blue-500/70" aria-hidden />
            <p className="text-sm">Chargement des événements…</p>
          </div>
        ) : (
          <div className="max-h-[min(72vh,calc(100dvh-15rem))] overflow-auto">
            <table className="w-max min-w-full border-separate border-spacing-0 text-left">
                <thead>
                  <tr className="sticky top-0 z-20">
                    <th
                      scope="col"
                      className="sticky left-0 z-30 border-b border-r border-white/[0.07] bg-zinc-950/95 px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-zinc-500 backdrop-blur-md shadow-[4px_0_12px_-4px_rgba(0,0,0,0.5)]"
                    >
                      #
                    </th>
                    {NORMALIZED_TABLE_COLUMNS.map((col) => (
                      <th
                        key={col.label}
                        scope="col"
                        className="border-b border-r border-white/[0.07] bg-zinc-950/90 px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-zinc-500 last:border-r-0"
                      >
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono text-[11px] leading-snug">
                  {rows.map((row, ri) => (
                    <tr
                      key={`${page}-${ri}`}
                      className="group transition-colors hover:bg-blue-500/[0.04] odd:bg-white/[0.015]"
                    >
                      <td
                        className="sticky left-0 z-10 border-b border-r border-white/[0.05] bg-zinc-950/90 px-3 py-2 text-zinc-500 tabular-nums shadow-[4px_0_12px_-4px_rgba(0,0,0,0.4)] backdrop-blur-sm group-hover:bg-zinc-900/95"
                      >
                        {page * PAGE_SIZE + ri + 1}
                      </td>
                      {NORMALIZED_TABLE_COLUMNS.map((col) => {
                        const v = getByPath(row, col.path);
                        const long =
                          col.label === "message" ||
                          col.label === "uri" ||
                          col.label === "user_agent" ||
                          col.label === "s3_key";
                        const display = formatCell(v, long ? 200 : 80);
                        const full = formatCell(v, 50_000);
                        return (
                          <td
                            key={col.label}
                            className="max-w-[min(14rem,28vw)] border-b border-r border-white/[0.05] px-3 py-2 align-top text-zinc-300 last:border-r-0"
                            title={full}
                          >
                            <span className="line-clamp-3 break-all">{display}</span>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  {rows.length === 0 && !loading && (
                    <tr>
                      <td
                        colSpan={NORMALIZED_TABLE_COLUMNS.length + 1}
                        className="px-6 py-16 text-center"
                      >
                        <p className="mx-auto max-w-md text-[15px] leading-relaxed text-zinc-500">
                          Aucun log renvoyé. Vérifie le bucket S3,{" "}
                          <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-400">
                            RAW_LOGS_*
                          </code>{" "}
                          et que l’API tourne (ex. port{" "}
                          <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-400">
                            8020
                          </code>
                          ).
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[13px] text-zinc-500">
          Page <span className="font-medium tabular-nums text-zinc-300">{page + 1}</span>
          {hasMore ? (
            <span className="text-zinc-600"> · page suivante disponible</span>
          ) : rows.length > 0 ? (
            <span className="text-zinc-600"> · fin du flux</span>
          ) : null}
        </p>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0 || loading}
            className="focus-ring inline-flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-zinc-900/50 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-white/15 hover:bg-zinc-800/50 disabled:pointer-events-none disabled:opacity-35"
          >
            <ChevronLeft size={18} aria-hidden />
            Précédent
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasMore || loading}
            className="focus-ring inline-flex items-center gap-1.5 rounded-xl border border-blue-500/20 bg-blue-500/10 px-4 py-2.5 text-sm font-medium text-blue-100 transition hover:bg-blue-500/20 disabled:pointer-events-none disabled:opacity-35"
          >
            Suivant
            <ChevronRight size={18} aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
