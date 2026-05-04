"use client";

import type { ReactNode } from "react";
import { Flame, Gauge, Shield, Skull } from "lucide-react";
import { useCountUp } from "@/hooks/useCountUp";
import type { SeverityFourCounts } from "@/lib/alertCatalogAggregates";

function formatInt(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}

function formatPct(n: number): string {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, minimumFractionDigits: 0 }).format(n);
}

const CARD_DEF = [
  {
    key: "critical" as const,
    label: "Critique",
    sub: "critical",
    icon: Skull,
    ambientMain: "analytics-ambient-strong",
    ambientCorner: "analytics-ambient",
    ring:
      "shadow-[0_0_52px_-14px_rgba(248,113,113,0.35)] ring-red-400/25 hover:shadow-[0_0_60px_-12px_rgba(248,113,113,0.42)]",
    bar: "from-red-500 via-red-600 to-rose-900/90",
    iconBg: "bg-red-500/15 text-red-200 ring-red-500/35",
    labelClass: "text-red-200",
    glowOrb: "from-red-500/22",
    glowOrb2: "from-red-400/10",
  },
  {
    key: "high" as const,
    label: "Élevé",
    sub: "high",
    icon: Flame,
    ambientMain: "analytics-ambient-strong",
    ambientCorner: "analytics-ambient-subtle",
    ring:
      "shadow-[0_0_46px_-18px_rgba(249,115,22,0.32)] ring-orange-400/22 hover:shadow-[0_0_54px_-14px_rgba(249,115,22,0.38)]",
    bar: "from-orange-500 via-amber-600 to-orange-950/90",
    iconBg: "bg-orange-500/15 text-orange-200 ring-orange-500/30",
    labelClass: "text-orange-200",
    glowOrb: "from-orange-500/20",
    glowOrb2: "from-amber-400/10",
  },
  {
    key: "medium" as const,
    label: "Moyen",
    sub: "medium",
    icon: Gauge,
    ambientMain: "analytics-ambient",
    ambientCorner: "analytics-ambient-subtle",
    ring:
      "shadow-[0_0_40px_-20px_rgba(250,204,21,0.18)] ring-amber-400/18 hover:shadow-[0_0_48px_-16px_rgba(250,204,21,0.26)]",
    bar: "from-amber-400 via-yellow-600/90 to-amber-950/80",
    iconBg: "bg-amber-500/14 text-amber-100 ring-amber-400/28",
    labelClass: "text-amber-100",
    glowOrb: "from-amber-400/16",
    glowOrb2: "from-yellow-400/8",
  },
  {
    key: "faible" as const,
    label: "Faible",
    sub: "low, info, autres",
    icon: Shield,
    ambientMain: "analytics-ambient",
    ambientCorner: "analytics-ambient-subtle",
    ring:
      "shadow-[0_0_38px_-20px_rgba(52,211,153,0.16)] ring-emerald-400/18 hover:shadow-[0_0_46px_-14px_rgba(52,211,153,0.22)]",
    bar: "from-emerald-500 via-teal-700/90 to-emerald-950/80",
    iconBg: "bg-emerald-500/12 text-emerald-100 ring-emerald-400/25",
    labelClass: "text-emerald-100",
    glowOrb: "from-emerald-500/14",
    glowOrb2: "from-teal-400/8",
  },
] as const;

function SeverityKpiCard({
  label,
  sub,
  icon,
  target,
  totalCatalog,
  accentClasses,
  staggerMs,
  loading,
}: {
  label: string;
  sub: string;
  icon: ReactNode;
  target: number | null;
  totalCatalog: number;
  accentClasses: (typeof CARD_DEF)[number];
  staggerMs: number;
  loading: boolean;
}) {
  const count = useCountUp(loading || target == null ? null : target, 900);
  const share = totalCatalog > 0 && target != null ? (100 * target) / totalCatalog : 0;

  return (
    <div
      className={`soc-severity-kpi-enter group relative flex min-h-[168px] flex-col overflow-hidden rounded-2xl border border-white/[0.09] bg-gradient-to-br from-zinc-950/95 via-zinc-900/65 to-zinc-950/90 p-5 ring-1 ring-white/[0.06] transition-[box-shadow,transform] duration-300 hover:-translate-y-0.5 hover:border-white/[0.14] ${accentClasses.ring}`}
      style={{ animationDelay: `${staggerMs}ms` }}
    >
      {/* Accent rail */}
      <div
        className={`pointer-events-none absolute inset-y-3 left-0 w-[5px] rounded-r-full bg-gradient-to-b ${accentClasses.bar} opacity-95 shadow-[0_0_20px_rgba(255,255,255,0.12)]`}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-y-5 left-[3px] w-px bg-white/25 blur-[1px]"
        aria-hidden
      />

      {/* Halos (même logique que Analytics KPI) */}
      <div
        className={`pointer-events-none absolute -right-10 -top-10 h-36 w-36 rounded-full bg-gradient-to-br ${accentClasses.glowOrb} to-transparent blur-3xl ${accentClasses.ambientMain}`}
      />
      <div
        className={`pointer-events-none absolute -bottom-7 -left-6 h-24 w-28 rounded-full bg-gradient-to-tr ${accentClasses.glowOrb2} to-transparent blur-2xl ${accentClasses.ambientCorner}`}
        style={{ animationDelay: "-3.5s" }}
      />

      {/* Grille tactique légère */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.17] [mask-image:linear-gradient(180deg,black,transparent_88%)]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)`,
          backgroundSize: "20px 20px",
        }}
        aria-hidden
      />

      <div className="relative flex flex-1 flex-col pl-1">
        <div className="flex items-start gap-3">
          <span
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ring-1 ${accentClasses.iconBg} shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition group-hover:scale-[1.03]`}
          >
            {icon}
          </span>
          <div className="min-w-0 flex-1 pt-0.5">
            <p
              className={`text-[11px] font-bold uppercase tracking-[0.2em] ${accentClasses.labelClass} drop-shadow-[0_0_12px_rgba(255,255,255,0.08)]`}
            >
              {label}
            </p>
            <p className="mt-3 font-mono text-4xl font-bold tabular-nums tracking-tight text-white drop-shadow-[0_2px_24px_rgba(0,0,0,0.45)] sm:text-5xl sm:leading-none">
              {loading || target == null ? (
                <span
                  className="inline-block h-[1.1em] w-16 max-w-[45%] animate-pulse rounded-md bg-zinc-700/80 align-middle"
                  aria-hidden
                />
              ) : (
                <span className="inline-block tabular-nums">{formatInt(count)}</span>
              )}
            </p>
          </div>
        </div>
        <div className="mt-auto space-y-1.5 pl-[3.75rem]">
          <p className="text-[11px] font-medium text-zinc-500">{sub}</p>
          {!loading && target != null && totalCatalog > 0 ? (
            <p className="text-[11px] text-zinc-500">
              <span className="font-mono text-zinc-400">{formatPct(share)}&nbsp;%</span> du catalogue
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function SeverityKpiCards({
  loading,
  severityFour,
  totalCatalog,
}: {
  loading: boolean;
  severityFour: SeverityFourCounts | null;
  totalCatalog: number;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {CARD_DEF.map((def, i) => {
        const Icon = def.icon;
        const target = loading || !severityFour ? null : severityFour[def.key];
        return (
          <SeverityKpiCard
            key={def.key}
            label={def.label}
            sub={def.sub}
            icon={<Icon size={22} strokeWidth={1.85} className="opacity-95" aria-hidden />}
            target={target}
            totalCatalog={totalCatalog}
            accentClasses={def}
            staggerMs={i * 95}
            loading={loading}
          />
        );
      })}
    </div>
  );
}
