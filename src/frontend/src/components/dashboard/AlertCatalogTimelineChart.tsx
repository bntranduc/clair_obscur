"use client";

import { useId, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import type { DayCountRow } from "@/lib/alertCatalogAggregates";

const TOOLTIP_STYLE = {
  borderRadius: 8,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(9,9,11,0.95)",
  padding: "8px 12px",
  fontSize: 12,
  color: "#e4e4e7",
  boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
};

/** Délai d’entrée (ms) : aligné sur l’animation en cascade des cartes criticité (~4×95 ms). */
const DEFAULT_ENTER_DELAY_MS = 400;

function formatInt(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}

function TimelineChartSkeleton({ enterDelayMs, reducedMotion }: { enterDelayMs: number; reducedMotion: boolean }) {
  const bars = useMemo(() => [38, 62, 44, 78, 52, 88, 46, 70, 55, 82, 48, 66], []);
  return (
    <div
      className={`relative h-[300px] w-full min-w-0 overflow-hidden rounded-xl border border-white/[0.07] bg-zinc-950/70 sm:h-[320px] ${
        reducedMotion ? "" : "soc-alert-timeline-enter"
      }`}
      style={reducedMotion ? undefined : { animationDelay: `${enterDelayMs}ms` }}
      role="status"
      aria-label="Chargement du graphique"
    >
      <div className="absolute inset-0 flex flex-col p-4 pt-6">
        <div className="mb-2 h-2 w-24 rounded bg-zinc-700/40" />
        <div className="flex min-h-0 flex-1 items-end justify-between gap-1.5 sm:gap-2">
          {bars.map((h, i) => (
            <div
              key={i}
              className="min-w-0 flex-1 rounded-t-md bg-gradient-to-t from-sky-600/25 to-cyan-400/20"
              style={{ height: `${h}%`, animationDelay: `${i * 45}ms` }}
            />
          ))}
        </div>
        <div className="mt-2 h-2 w-full rounded bg-zinc-800/50" />
      </div>
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-b from-cyan-500/[0.07] via-transparent to-transparent opacity-80 ${
          reducedMotion ? "" : "animate-pulse"
        }`}
        aria-hidden
      />
    </div>
  );
}

export default function AlertCatalogTimelineChart({
  dayRows,
  loading = false,
  enterDelayMs = DEFAULT_ENTER_DELAY_MS,
}: {
  dayRows: DayCountRow[];
  /** Affiche un placeholder animé pendant le chargement des alertes. */
  loading?: boolean;
  /** Délai avant l’entrée du bloc (synchronisé avec les KPI). */
  enterDelayMs?: number;
}) {
  const gradId = useId().replace(/:/g, "");
  const reducedMotion = usePrefersReducedMotion();
  const lineAnimBegin = reducedMotion ? 0 : enterDelayMs + 160;
  const lineAnimDuration = reducedMotion ? 0 : 1150;

  if (loading) {
    return <TimelineChartSkeleton enterDelayMs={enterDelayMs} reducedMotion={reducedMotion} />;
  }

  if (dayRows.length === 0) {
    return (
      <p
        className={`rounded-xl border border-white/[0.06] bg-zinc-950/40 px-4 py-8 text-center text-sm text-zinc-500 ${
          reducedMotion ? "" : "soc-alert-timeline-enter"
        }`}
        style={reducedMotion ? undefined : { animationDelay: `${enterDelayMs}ms` }}
      >
        Aucune date exploitable sur les alertes (<code className="text-zinc-400">detection.attack_start_time</code> ou{" "}
        <code className="text-zinc-400">attack_end_time</code>) pour tracer la courbe.
      </p>
    );
  }

  return (
    <div
      className={`h-[300px] w-full min-w-0 sm:h-[320px] ${reducedMotion ? "" : "soc-alert-timeline-enter"}`}
      style={reducedMotion ? undefined : { animationDelay: `${enterDelayMs}ms` }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={dayRows} margin={{ top: 8, left: 4, right: 12, bottom: 4 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="day" stroke="#71717a" tick={{ fill: "#a1a1aa", fontSize: 10 }} tickMargin={6} />
          <YAxis
            stroke="#71717a"
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            allowDecimals={false}
            width={36}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [formatInt(typeof v === "number" ? v : Number(v)), "Alertes"]}
            labelFormatter={(label) => {
              if (label == null) return "";
              if (typeof label === "string" && /^\d{2}-\d{2}$/.test(label)) {
                const row = dayRows.find((d) => d.day === label);
                return row?.full ? String(row.full) : String(label);
              }
              return String(label);
            }}
          />
          <Area
            type="monotone"
            dataKey="count"
            name="Alertes"
            stroke="#38bdf8"
            strokeWidth={2.5}
            fill={`url(#${gradId})`}
            dot={{ fill: "#38bdf8", strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: "#7dd3fc" }}
            isAnimationActive={!reducedMotion}
            animationDuration={lineAnimDuration}
            animationBegin={lineAnimBegin}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
