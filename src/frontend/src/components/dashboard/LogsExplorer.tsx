"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { NormalizedEventsTable } from "@/components/dashboard/NormalizedEventsTable";
import { PredictAlertsCards } from "@/components/dashboard/PredictAlertsCards";
import {
  fetchS3LogObjects,
  fetchS3LogSample,
  type ListS3ObjectsResponse,
  type S3SampleResponse,
} from "@/lib/api";
import { getModelPredictUrl } from "@/lib/modelPredict";
import { postPredict } from "@/lib/predictClient";

type Props = {
  title: string;
  /** Sélectionne automatiquement le premier fichier S3 pour afficher le tableau tout de suite. */
  autoSelectFirst?: boolean;
};

export function LogsExplorer({ title, autoSelectFirst }: Props) {
  const [list, setList] = useState<ListS3ObjectsResponse | null>(null);
  const [listErr, setListErr] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [sample, setSample] = useState<S3SampleResponse | null>(null);
  const [sampleErr, setSampleErr] = useState<string | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);

  const [predictLoading, setPredictLoading] = useState(false);
  const [predictErr, setPredictErr] = useState<string | null>(null);
  const [predictAlerts, setPredictAlerts] = useState<Record<string, unknown>[]>([]);
  const [predictRaw, setPredictRaw] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    setListErr(null);
    try {
      const data = await fetchS3LogObjects(100);
      setList(data);
    } catch (e) {
      setListErr(e instanceof Error ? e.message : String(e));
      setList(null);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const loadSample = useCallback(async (key: string) => {
    setSelectedKey(key);
    setLoadingSample(true);
    setSampleErr(null);
    setSample(null);
    setPredictErr(null);
    setPredictAlerts([]);
    setPredictRaw(null);
    try {
      const data = await fetchS3LogSample(key, { limitLines: 120 });
      setSample(data);
    } catch (e) {
      setSampleErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSample(false);
    }
  }, []);

  const runPredictOnSample = useCallback(async () => {
    if (!sample?.logs?.length) return;
    setPredictErr(null);
    setPredictAlerts([]);
    setPredictRaw(null);
    setPredictLoading(true);
    try {
      const events = sample.logs as Record<string, unknown>[];
      const { alerts, rawText } = await postPredict(events);
      setPredictAlerts(alerts);
      setPredictRaw(rawText);
    } catch (e) {
      setPredictErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPredictLoading(false);
    }
  }, [sample]);

  useEffect(() => {
    if (!autoSelectFirst || !list?.objects.length || selectedKey) return;
    void loadSample(list.objects[0].key);
  }, [autoSelectFirst, list, selectedKey, loadSample]);

  return (
    <div className="space-y-8 max-w-[100vw]">
      <div>
        <h1 className="text-2xl font-semibold text-white">{title}</h1>
        <p className="text-zinc-500 text-sm mt-1">
          Bucket <span className="text-zinc-300">{list?.bucket ?? "…"}</span> — préfixe{" "}
          <span className="text-zinc-300 font-mono text-xs">{list?.prefix ?? "…"}</span>
        </p>
        <p className="text-zinc-600 text-xs mt-2">
          Une colonne par champ (<span className="font-mono text-zinc-500">NormalizedEvent</span> +{" "}
          <span className="font-mono text-zinc-500">RawRef</span>) — valeurs lues depuis le JSON API,
          pas de bloc JSON dans les cellules.
        </p>
      </div>

      <section className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <span className="text-sm font-medium text-zinc-300">Fichiers S3</span>
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
          <p className="p-6 text-zinc-500 text-sm">Aucun objet sous ce préfixe.</p>
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
                      selectedKey === o.key ? "bg-indigo-500/10" : ""
                    }`}
                    onClick={() => void loadSample(o.key)}
                  >
                    <td className="px-4 py-2 font-mono text-xs text-indigo-300 break-all">{o.key}</td>
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

      <section className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden min-h-[240px]">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-3 border-b border-white/10">
          <div>
            <span className="text-sm font-medium text-zinc-300">Tableau des événements</span>
            {selectedKey && (
              <p className="text-xs font-mono text-zinc-500 mt-1 break-all">{selectedKey}</p>
            )}
          </div>
          {sample && sample.logs.length > 0 && !loadingSample && (
            <button
              type="button"
              disabled={predictLoading}
              onClick={() => void runPredictOnSample()}
              className="inline-flex items-center justify-center gap-2 shrink-0 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              {predictLoading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              Prédire (modèle)
            </button>
          )}
        </div>
        {sample && sample.logs.length > 0 && (
          <p className="px-4 py-2 text-[11px] text-zinc-600 border-b border-white/5">
            Envoi des lignes chargées vers <span className="font-mono text-zinc-500">{getModelPredictUrl()}</span>{" "}
            (même API que « Tester modèle »).
          </p>
        )}
        {!selectedKey && (
          <p className="p-6 text-zinc-500 text-sm">Sélectionne un fichier ci-dessus.</p>
        )}
        {selectedKey && loadingSample && <p className="p-6 text-zinc-500 text-sm">Lecture…</p>}
        {sampleErr && <p className="p-6 text-red-400 text-sm whitespace-pre-wrap">{sampleErr}</p>}
        {sample && !loadingSample && (
          <>
            <NormalizedEventsTable
              logs={sample.logs as Record<string, unknown>[]}
              truncated={sample.truncated}
              offsetLines={sample.offset_lines}
              limitLines={sample.limit_lines}
            />
            {(predictErr || predictAlerts.length > 0 || predictRaw) && (
              <div className="p-4 border-t border-white/10 space-y-4 bg-black/20">
                {predictErr && (
                  <div className="rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-200 whitespace-pre-wrap">
                    {predictErr}
                  </div>
                )}
                <PredictAlertsCards alerts={predictAlerts} />
                {predictRaw && (
                  <details className="group">
                    <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">JSON brut</summary>
                    <pre className="mt-2 text-[11px] text-zinc-400 font-mono whitespace-pre-wrap break-words bg-black/50 rounded-lg p-3 border border-white/[0.06] max-h-64 overflow-auto">
                      {predictRaw}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </>
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
