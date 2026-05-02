"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, RefreshCw, Search } from "lucide-react";
import {
  fetchPredictionFile,
  fetchPredictionObjects,
  type AlertsPool,
  type ListPredictionsResponse,
  type PredictionFileResponse,
} from "@/lib/api";
import { alertToCardModel, type AlertCardModel } from "@/lib/alertPresentation";

export function AlertsBoard() {
  const [pool, setPool] = useState<AlertsPool>("tmp");
  const [list, setList] = useState<ListPredictionsResponse | null>(null);
  const [listErr, setListErr] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [file, setFile] = useState<PredictionFileResponse | null>(null);
  const [fileErr, setFileErr] = useState<string | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);

  const [query, setQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    setListErr(null);
    try {
      const data = await fetchPredictionObjects(pool, 200);
      setList(data);
    } catch (e) {
      setListErr(e instanceof Error ? e.message : String(e));
      setList(null);
    } finally {
      setLoadingList(false);
    }
  }, [pool]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const loadFile = useCallback(
    async (key: string) => {
      setSelectedKey(key);
      setLoadingFile(true);
      setFileErr(null);
      setFile(null);
      setExpandedId(null);
      try {
        const data = await fetchPredictionFile(pool, key);
        setFile(data);
      } catch (e) {
        setFileErr(e instanceof Error ? e.message : String(e));
      } finally {
        setLoadingFile(false);
      }
    },
    [pool]
  );

  useEffect(() => {
    if (!list?.objects.length || selectedKey) return;
    void loadFile(list.objects[0].key);
  }, [list, selectedKey, loadFile]);

  const cards: AlertCardModel[] = useMemo(() => {
    if (!file?.alerts.length) return [];
    return file.alerts.map((a, i) => alertToCardModel(a, i));
  }, [file?.alerts]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return cards;
    return cards.filter(
      (c) =>
        c.challengeId.toLowerCase().includes(q) ||
        c.attackType.toLowerCase().includes(q) ||
        c.attackerIps.some((ip) => ip.toLowerCase().includes(q)) ||
        c.victimAccounts.some((v) => v.toLowerCase().includes(q)) ||
        (c.indicatorsPreview?.toLowerCase().includes(q) ?? false)
    );
  }, [cards, query]);

  const shortKey = selectedKey?.split("/").pop() ?? "";

  return (
    <div className="flex flex-col lg:flex-row gap-6 min-h-[calc(100vh-8rem)]">
      {/* Sources */}
      <aside className="lg:w-72 shrink-0 flex flex-col rounded-2xl border border-white/[0.08] bg-gradient-to-b from-zinc-900/80 to-black/40 overflow-hidden">
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-white tracking-tight">Sources</h2>
            <button
              type="button"
              onClick={() => void loadList()}
              disabled={loadingList}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 disabled:opacity-40 transition-colors"
              aria-label="Actualiser"
            >
              <RefreshCw size={16} className={loadingList ? "animate-spin" : ""} />
            </button>
          </div>
          <div className="flex rounded-lg bg-black/40 p-0.5 border border-white/[0.06]">
            <button
              type="button"
              onClick={() => {
                setPool("prod");
                setSelectedKey(null);
                setFile(null);
              }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                pool === "prod" ? "bg-white/15 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Prod
            </button>
            <button
              type="button"
              onClick={() => {
                setPool("tmp");
                setSelectedKey(null);
                setFile(null);
              }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                pool === "tmp" ? "bg-amber-500/25 text-amber-100 shadow-sm" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Tmp
            </button>
          </div>
          <p className="text-[11px] text-zinc-500 leading-snug">
            {list?.bucket ?? "…"} · <span className="font-mono text-zinc-400">{list?.prefix ?? "predictions/"}</span>
          </p>
        </div>
        <div className="flex-1 overflow-y-auto max-h-64 lg:max-h-none min-h-0">
          {loadingList && <p className="p-4 text-sm text-zinc-500">Chargement…</p>}
          {listErr && <p className="p-4 text-sm text-red-400">{listErr}</p>}
          {!loadingList && list && list.objects.length === 0 && (
            <p className="p-4 text-sm text-zinc-500">Aucun fichier.</p>
          )}
          {!loadingList &&
            list?.objects.map((o) => (
              <button
                key={o.key}
                type="button"
                onClick={() => void loadFile(o.key)}
                className={`w-full text-left px-4 py-3 border-b border-white/[0.04] transition-colors ${
                  selectedKey === o.key
                    ? "bg-amber-500/10 border-l-2 border-l-amber-400 pl-[14px]"
                    : "hover:bg-white/[0.04] border-l-2 border-l-transparent"
                }`}
              >
                <div className="font-mono text-[11px] text-zinc-300 truncate" title={o.key}>
                  {o.key.replace(/^.*\//, "")}
                </div>
                <div className="flex justify-between mt-1 text-[10px] text-zinc-500">
                  <span>{formatBytes(o.size)}</span>
                  <span className="truncate max-w-[9rem]">{o.last_modified?.slice(0, 16) ?? ""}</span>
                </div>
              </button>
            ))}
        </div>
      </aside>

      {/* Contenu principal */}
      <div className="flex-1 flex flex-col min-w-0 rounded-2xl border border-white/[0.08] bg-gradient-to-br from-zinc-900/40 via-black/20 to-transparent overflow-hidden">
        <header className="p-5 border-b border-white/[0.06] space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-white tracking-tight">Incidents détectés</h1>
              <p className="text-sm text-zinc-500 mt-1">
                {file && !loadingFile ? (
                  <>
                    <span className="text-zinc-400">{filtered.length}</span> incident(s) affiché(s)
                    {query && cards.length !== filtered.length ? (
                      <span className="text-zinc-600"> · sur {cards.length}</span>
                    ) : null}
                    {shortKey ? (
                      <span className="block mt-1 font-mono text-xs text-zinc-600 truncate max-w-xl">
                        {shortKey}
                      </span>
                    ) : null}
                  </>
                ) : (
                  "Sélectionnez une source ou attendez le chargement."
                )}
              </p>
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
            <input
              type="search"
              placeholder="Filtrer par type, IP, compte, indicateur…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-black/35 border border-white/[0.08] text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/40"
            />
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loadingFile && (
            <div className="flex items-center justify-center py-20 text-zinc-500 text-sm">Chargement du fichier…</div>
          )}
          {fileErr && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
              {fileErr}
            </div>
          )}
          {!loadingFile && file && file.alerts.length === 0 && (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-8 py-16 text-center">
              <p className="text-zinc-400 text-sm">Aucun incident dans ce fichier.</p>
              <p className="text-zinc-600 text-xs mt-2">La liste `alerts` est vide (sortie worker ou fenêtre sans signal).</p>
            </div>
          )}
          {!loadingFile &&
            file &&
            filtered.map((card, idx) => (
              <article
                key={`${selectedKey ?? "x"}-${idx}-${card.id}`}
                className="rounded-2xl border border-white/[0.07] bg-gradient-to-br from-zinc-900/90 to-black/60 shadow-lg shadow-black/20 overflow-hidden"
              >
                <div className="px-5 py-4 flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.05]">
                  <div className="space-y-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-amber-500/15 text-amber-200 border border-amber-500/25">
                        {card.challengeId.replace(/_/g, " ")}
                      </span>
                      {card.detectionTimeSec != null && (
                        <span className="text-[11px] text-zinc-500">détection ~ {card.detectionTimeSec}s</span>
                      )}
                    </div>
                    <h3 className="text-lg font-medium text-white capitalize">{card.attackType.replace(/_/g, " ")}</h3>
                  </div>
                </div>

                <div className="px-5 py-4 grid sm:grid-cols-2 gap-4 text-sm">
                  <div className="space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Fenêtre</div>
                    <p className="text-zinc-300">{card.windowLabel ?? "—"}</p>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      Adresses sources
                    </div>
                    <p className="text-zinc-300 font-mono text-xs break-all">
                      {card.attackerIps.length ? card.attackerIps.join(", ") : "—"}
                    </p>
                  </div>
                  <div className="space-y-1 sm:col-span-2">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      Comptes / victimes
                    </div>
                    <p className="text-zinc-300">
                      {card.victimAccounts.length ? card.victimAccounts.join(", ") : "—"}
                    </p>
                  </div>
                  {card.indicatorsPreview && (
                    <div className="space-y-1 sm:col-span-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                        Indicateurs
                      </div>
                      <p className="text-zinc-400 text-xs leading-relaxed">{card.indicatorsPreview}</p>
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => setExpandedId((id) => (id === card.id ? null : card.id))}
                  className="w-full flex items-center justify-center gap-2 py-2.5 text-xs text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03] border-t border-white/[0.05] transition-colors"
                >
                  {expandedId === card.id ? (
                    <>
                      <ChevronDown size={14} /> Masquer le JSON
                    </>
                  ) : (
                    <>
                      <ChevronRight size={14} /> Détails techniques (JSON)
                    </>
                  )}
                </button>
                {expandedId === card.id && (
                  <pre className="text-[11px] leading-relaxed text-zinc-400 px-5 pb-4 overflow-x-auto border-t border-white/[0.04] bg-black/30 p-4 font-mono">
                    {JSON.stringify(card.raw, null, 2)}
                  </pre>
                )}
              </article>
            ))}
        </div>
      </div>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
