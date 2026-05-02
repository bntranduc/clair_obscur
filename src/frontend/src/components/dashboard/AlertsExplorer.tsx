"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchPredictionFile,
  fetchPredictionObjects,
  type AlertsPool,
  type ListPredictionsResponse,
  type PredictionFileResponse,
} from "@/lib/api";

type Props = {
  autoSelectFirst?: boolean;
};

export function AlertsExplorer({ autoSelectFirst }: Props) {
  const [pool, setPool] = useState<AlertsPool>("tmp");
  const [list, setList] = useState<ListPredictionsResponse | null>(null);
  const [listErr, setListErr] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [file, setFile] = useState<PredictionFileResponse | null>(null);
  const [fileErr, setFileErr] = useState<string | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);

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
    if (!autoSelectFirst || !list?.objects.length || selectedKey) return;
    void loadFile(list.objects[0].key);
  }, [autoSelectFirst, list, selectedKey, loadFile]);

  return (
    <div className="space-y-8 max-w-[100vw]">
      <div>
        <h1 className="text-2xl font-semibold text-white">Fichiers prédictions (JSON)</h1>
        <p className="text-zinc-500 text-sm mt-1">
          Bucket{" "}
          <span className="text-zinc-300">{list?.bucket ?? "…"}</span> — préfixe{" "}
          <span className="text-zinc-300 font-mono text-xs">{list?.prefix ?? "predictions/"}</span>
        </p>
        <div className="flex flex-wrap gap-3 mt-4 items-center">
          <span className="text-xs text-zinc-500">Pool</span>
          <div className="flex rounded-lg border border-white/10 overflow-hidden text-sm">
            <button
              type="button"
              onClick={() => {
                setPool("prod");
                setSelectedKey(null);
                setFile(null);
              }}
              className={`px-3 py-1.5 ${pool === "prod" ? "bg-indigo-600 text-white" : "bg-white/5 text-zinc-400 hover:bg-white/10"}`}
            >
              prod
            </button>
            <button
              type="button"
              onClick={() => {
                setPool("tmp");
                setSelectedKey(null);
                setFile(null);
              }}
              className={`px-3 py-1.5 border-l border-white/10 ${pool === "tmp" ? "bg-indigo-600 text-white" : "bg-white/5 text-zinc-400 hover:bg-white/10"}`}
            >
              tmp
            </button>
          </div>
        </div>
      </div>

      <section className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <span className="text-sm font-medium text-zinc-300">Fichiers prédictions</span>
          <button
            type="button"
            onClick={() => void loadList()}
            disabled={loadingList}
            className="text-xs px-3 py-1.5 rounded-md bg-white/10 hover:bg-white/15 disabled:opacity-50 text-zinc-200"
          >
            Actualiser
          </button>
        </div>
        {loadingList && <p className="p-6 text-zinc-500 text-sm">Chargement…</p>}
        {listErr && <p className="p-6 text-red-400 text-sm whitespace-pre-wrap">{listErr}</p>}
        {!loadingList && list && list.objects.length === 0 && (
          <p className="p-6 text-zinc-500 text-sm">Aucun fichier sous ce préfixe.</p>
        )}
        {!loadingList && list && list.objects.length > 0 && (
          <div className="max-h-56 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-zinc-950/95 text-left text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Clé</th>
                  <th className="px-4 py-2 font-medium w-28">Taille</th>
                  <th className="px-4 py-2 font-medium">Modifié</th>
                </tr>
              </thead>
              <tbody>
                {list.objects.map((o) => (
                  <tr
                    key={o.key}
                    className={`border-t border-white/5 hover:bg-white/[0.04] cursor-pointer ${
                      selectedKey === o.key ? "bg-amber-500/10" : ""
                    }`}
                    onClick={() => void loadFile(o.key)}
                  >
                    <td className="px-4 py-2 font-mono text-xs text-amber-200/90 break-all">{o.key}</td>
                    <td className="px-4 py-2 text-zinc-400">{formatBytes(o.size)}</td>
                    <td className="px-4 py-2 text-zinc-500 whitespace-nowrap">
                      {o.last_modified ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden min-h-[200px]">
        <div className="px-4 py-3 border-b border-white/10">
          <span className="text-sm font-medium text-zinc-300">Contenu</span>
          {selectedKey && (
            <p className="text-xs font-mono text-zinc-500 mt-1 break-all">{selectedKey}</p>
          )}
        </div>
        {!selectedKey && (
          <p className="p-6 text-zinc-500 text-sm">Sélectionne un fichier JSON.</p>
        )}
        {selectedKey && loadingFile && <p className="p-6 text-zinc-500 text-sm">Lecture…</p>}
        {fileErr && <p className="p-6 text-red-400 text-sm whitespace-pre-wrap">{fileErr}</p>}
        {file && !loadingFile && (
          <div className="p-4 space-y-4">
            {file.meta && (
              <div>
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                  meta
                </h3>
                <pre className="text-xs text-zinc-300 bg-black/40 rounded-lg p-3 overflow-x-auto border border-white/5">
                  {JSON.stringify(file.meta, null, 2)}
                </pre>
              </div>
            )}
            <div>
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                alerts ({file.alerts.length})
              </h3>
              {file.alerts.length === 0 ? (
                <p className="text-sm text-zinc-500">Liste vide.</p>
              ) : (
                <ul className="space-y-3 max-h-[min(60vh,520px)] overflow-y-auto">
                  {file.alerts.map((alert, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-white/10 bg-black/30 overflow-hidden"
                    >
                      <div className="px-3 py-2 border-b border-white/5 text-xs text-zinc-500 font-mono">
                        #{i + 1}
                        {typeof alert === "object" && alert !== null && "challenge_id" in alert && (
                          <span className="text-amber-200/80 ml-2">
                            {(alert as { challenge_id?: string }).challenge_id}
                          </span>
                        )}
                      </div>
                      <pre className="text-[11px] text-zinc-300 p-3 overflow-x-auto whitespace-pre-wrap break-words">
                        {JSON.stringify(alert, null, 2)}
                      </pre>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
