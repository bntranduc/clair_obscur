"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Info, Loader2, Network, RefreshCw } from "lucide-react";
import {
  fetchAlertClustering,
  type AlertClusteringNode,
  type AlertClusteringResponse,
} from "@/lib/api";
import type { ForceGraphMethods } from "react-force-graph-2d";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex items-center justify-center bg-[radial-gradient(ellipse_at_50%_20%,rgba(14,116,144,0.12),transparent_50%),#05080c]">
      <Loader2 className="h-12 w-12 animate-spin text-cyan-400/90" aria-hidden />
    </div>
  ),
});

const CLUSTER_COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#14b8a6"];

function nodeColor(n: AlertClusteringNode): string {
  const c = n.cluster_id;
  if (c < 0) return "#71717a";
  const i = ((c % CLUSTER_COLORS.length) + CLUSTER_COLORS.length) % CLUSTER_COLORS.length;
  return CLUSTER_COLORS[i] ?? "#3b82f6";
}

export default function AlertClusterGraphPanel() {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const [eps, setEps] = useState(1.05);
  const [minSamples, setMinSamples] = useState(2);
  const [maxNeighbors, setMaxNeighbors] = useState(3);
  const [data, setData] = useState<AlertClusteringResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLegend, setShowLegend] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchAlertClustering({
        eps,
        min_samples: minSamples,
        max_neighbors: maxNeighbors,
      });
      setData(r);
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "Erreur réseau");
    } finally {
      setLoading(false);
    }
  }, [eps, minSamples, maxNeighbors]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    const nodes = data.nodes.map((n) => ({
      ...n,
      color: nodeColor(n),
    }));
    const links = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      value: e.weight,
    }));
    return { nodes, links };
  }, [data]);

  const handleEngineStop = useCallback(() => {
    fgRef.current?.zoomToFit(400, 80);
  }, []);

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-[#05080c]">
      {/* Barre d’outils — verre, compacte */}
      <header className="relative z-30 flex shrink-0 flex-col gap-3 border-b border-white/[0.08] bg-zinc-950/75 px-4 py-3 shadow-[0_8px_32px_-12px_rgba(0,0,0,0.7)] backdrop-blur-xl sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4 sm:py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/20 to-sky-600/15 ring-1 ring-cyan-500/25">
            <Network className="h-5 w-5 text-cyan-300" aria-hidden />
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold tracking-tight text-white sm:text-xl">Clusters d’alertes</h1>
            <p className="hidden text-[12px] text-zinc-500 sm:block">
              DBSCAN · voisins intra-cluster · catalogue{" "}
              <code className="rounded bg-zinc-800/80 px-1 font-mono text-[10px] text-zinc-400">GET /api/v1/alerts</code>
            </p>
          </div>
        </div>

        <div className="flex flex-1 flex-wrap items-end gap-3 sm:justify-end lg:max-w-[52rem]">
          <label className="flex min-w-[9rem] flex-1 flex-col gap-1 text-[11px] font-medium text-zinc-500 sm:max-w-[11rem]">
            <span className="text-zinc-400">ε (DBSCAN)</span>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.05}
                value={eps}
                onChange={(e) => setEps(Number(e.target.value))}
                className="h-2 w-full flex-1 cursor-pointer rounded-full bg-zinc-800 accent-cyan-500"
              />
              <span className="w-10 shrink-0 font-mono text-[12px] tabular-nums text-cyan-200/95">{eps.toFixed(2)}</span>
            </div>
          </label>
          <label className="flex w-[5.5rem] flex-col gap-1 text-[11px] font-medium text-zinc-500">
            <span className="text-zinc-400">Min.</span>
            <input
              type="number"
              min={2}
              max={12}
              value={minSamples}
              onChange={(e) => setMinSamples(Math.max(2, Number(e.target.value) || 2))}
              className="rounded-lg border border-white/[0.1] bg-zinc-950/90 px-2 py-1.5 font-mono text-sm text-white ring-1 ring-white/[0.04] focus:border-cyan-500/40 focus:outline-none"
            />
          </label>
          <label className="flex w-[5.5rem] flex-col gap-1 text-[11px] font-medium text-zinc-500">
            <span className="text-zinc-400">Voisins</span>
            <input
              type="number"
              min={1}
              max={10}
              value={maxNeighbors}
              onChange={(e) => setMaxNeighbors(Math.min(12, Math.max(1, Number(e.target.value) || 1)))}
              className="rounded-lg border border-white/[0.1] bg-zinc-950/90 px-2 py-1.5 font-mono text-sm text-white ring-1 ring-white/[0.04] focus:border-cyan-500/40 focus:outline-none"
            />
          </label>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            title="Recalculer avec les paramètres ci-dessus"
            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border border-cyan-500/25 bg-gradient-to-r from-cyan-950/80 to-sky-950/60 px-4 text-[13px] font-semibold text-cyan-100 shadow-[0_0_24px_-8px_rgba(34,211,238,0.35)] transition hover:border-cyan-400/40 hover:from-cyan-900/90 hover:to-sky-900/70 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden />
            Recalculer
          </button>
        </div>

        {data ? (
          <div className="flex w-full flex-wrap gap-x-4 gap-y-1 border-t border-white/[0.06] pt-2 text-[11px] text-zinc-500 sm:w-auto sm:border-0 sm:pt-0">
            <span>
              <span className="text-zinc-500">Alertes </span>
              <span className="font-mono font-semibold text-zinc-200">{data.meta.count}</span>
            </span>
            <span className="text-zinc-700">·</span>
            <span>
              <span className="text-zinc-500">Clusters </span>
              <span className="font-mono font-semibold text-zinc-200">{data.meta.n_clusters}</span>
            </span>
            <span className="text-zinc-700">·</span>
            <span>
              <span className="text-zinc-500">Bruit </span>
              <span className="font-mono font-semibold text-zinc-200">{data.meta.noise_count}</span>
            </span>
            <span className="text-zinc-700">·</span>
            <span>
              <span className="text-zinc-500">Arêtes </span>
              <span className="font-mono font-semibold text-zinc-200">{data.edges.length}</span>
            </span>
          </div>
        ) : null}
      </header>

      {error ? (
        <div className="shrink-0 border-b border-amber-500/25 bg-amber-500/10 px-4 py-2 text-[13px] text-amber-100">{error}</div>
      ) : null}

      {/* Zone graphe — occupe tout l’espace restant */}
      <div className="relative min-h-0 flex-1 overflow-hidden">
        {/* Fond spatial */}
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_120%_80%_at_50%_-20%,rgba(34,211,238,0.08),transparent_55%),radial-gradient(ellipse_80%_60%_at_100%_100%,rgba(59,130,246,0.06),transparent_50%),linear-gradient(180deg,#05080c_0%,#060a10_50%,#05080c_100%)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage: `linear-gradient(rgba(56,189,248,0.04) 1px, transparent 1px),
              linear-gradient(90deg, rgba(56,189,248,0.03) 1px, transparent 1px)`,
            backgroundSize: "48px 48px",
          }}
          aria-hidden
        />

        {loading ? (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-[#05080c]/55 backdrop-blur-[2px]">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-10 w-10 animate-spin text-cyan-400/90" aria-hidden />
              <span className="text-[12px] font-medium text-zinc-500">Chargement du graphe…</span>
            </div>
          </div>
        ) : null}

        <div className="absolute inset-0 min-h-[12rem]">
          {data && data.nodes.length === 0 && !loading ? (
            <div className="flex h-full items-center justify-center px-6 text-center">
              <p className="max-w-md text-[14px] leading-relaxed text-zinc-500">
                Aucune alerte dans le catalogue : rien à afficher.
              </p>
            </div>
          ) : (
            <ForceGraph2D
              ref={fgRef}
              graphData={graphData}
              backgroundColor="rgba(0,0,0,0)"
              nodeLabel={(n: object) => {
                const node = n as AlertClusteringNode & { color?: string };
                const t = node.title?.trim();
                return [node.id, node.label, node.severity, t ? `— ${t}` : ""].filter(Boolean).join("\n");
              }}
              nodeColor={(n: object) => (n as { color?: string }).color ?? "#71717a"}
              nodeRelSize={6}
              linkColor={() => "rgba(56, 189, 248, 0.42)"}
              linkWidth={1.35}
              linkDirectionalParticles={graphData.links.length > 0 ? 2 : 0}
              linkDirectionalParticleSpeed={0.004}
              linkDirectionalParticleWidth={1.5}
              linkDirectionalParticleColor={() => "rgba(125, 211, 252, 0.75)"}
              cooldownTicks={140}
              d3AlphaDecay={0.022}
              d3VelocityDecay={0.35}
              onEngineStop={handleEngineStop}
              enablePointerInteraction
              enableZoomInteraction
              enablePanInteraction
              minZoom={0.35}
              maxZoom={8}
            />
          )}
        </div>

        {/* Légende / aide — repliable, coin bas-gauche */}
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 z-10 flex justify-between gap-2 p-3 sm:p-4">
          <button
            type="button"
            onClick={() => setShowLegend((v) => !v)}
            className="pointer-events-auto flex items-center gap-2 rounded-full border border-white/[0.1] bg-zinc-950/85 px-3 py-1.5 text-[11px] font-medium text-zinc-400 shadow-lg backdrop-blur-md transition hover:border-white/[0.18] hover:text-zinc-200"
          >
            <Info size={14} className="text-cyan-400/90" aria-hidden />
            {showLegend ? "Masquer l’aide" : "Aide & traits"}
          </button>
        </div>

        {showLegend && data ? (
          <div className="pointer-events-auto absolute bottom-14 left-3 right-3 z-20 max-h-[40vh] overflow-y-auto rounded-xl border border-white/[0.1] bg-zinc-950/92 p-4 text-[12px] leading-relaxed text-zinc-400 shadow-2xl backdrop-blur-xl sm:left-4 sm:max-w-xl">
            <p className="font-medium text-zinc-200">Traits utilisés</p>
            <p className="mt-2 text-zinc-500">{data.meta.feature_columns.join(", ")}.</p>
            <p className="mt-3 text-zinc-500">
              Les liens relient les alertes les plus proches <span className="text-zinc-400">dans le même cluster</span>{" "}
              (k-voisins). Augmentez ε pour fusionner des groupes ; diminuez-le pour en créer davantage. Molette : zoom,
              glisser : déplacer.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
