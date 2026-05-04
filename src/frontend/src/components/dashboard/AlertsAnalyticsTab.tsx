"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bell,
  Gauge,
  Loader2,
  RefreshCw,
  Shield,
  Skull,
  Target,
  Timer,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchAllAlerts } from "@/lib/api";
import type { AlertCatalogItem, AlertsCatalogResponse } from "@/types/alertsCatalog";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
  info: "#64748b",
};

const PIE_ORDER = ["critical", "high", "medium", "low", "info", "autre"];

const TOOLTIP_STYLE = {
  borderRadius: 8,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(9,9,11,0.95)",
  padding: "8px 12px",
  fontSize: 12,
  color: "#e4e4e7",
  boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
};

function formatInt(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}

function formatPct(n: number): string {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, minimumFractionDigits: 0 }).format(n);
}

function normSeverity(s: string | undefined): string {
  const x = (s || "autre").toLowerCase().trim();
  if (["critical", "high", "medium", "low", "info"].includes(x)) return x;
  return "autre";
}

function attackLabel(a: AlertCatalogItem): string {
  return (a.detection?.attack_type || a.challenge_id || "inconnu").trim() || "inconnu";
}

function dayKeyFromIso(iso: string | undefined): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString().slice(0, 10);
  } catch {
    return null;
  }
}

function Kpi({
  icon,
  label,
  value,
  sub,
  accent,
  importance = "medium",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  accent: "blue" | "red" | "amber" | "emerald" | "violet";
  importance?: "high" | "medium" | "low";
}) {
  const ring =
    accent === "blue"
      ? importance === "high"
        ? "ring-blue-400/30"
        : "ring-blue-500/20"
      : accent === "red"
        ? importance === "high"
          ? "ring-red-400/35"
          : "ring-red-500/20"
        : accent === "amber"
          ? "ring-amber-500/20"
          : accent === "violet"
            ? "ring-violet-500/20"
            : "ring-emerald-500/20";
  const glow =
    accent === "blue"
      ? "from-blue-500/12"
      : accent === "red"
        ? "from-red-500/14"
        : accent === "amber"
          ? "from-amber-500/12"
          : accent === "violet"
            ? "from-violet-500/12"
            : "from-emerald-500/10";
  const ambient =
    importance === "high"
      ? "analytics-ambient-strong"
      : importance === "medium"
        ? "analytics-ambient"
        : "analytics-ambient-subtle";
  const orbMain =
    importance === "high"
      ? "-right-8 -top-8 h-32 w-32 blur-3xl"
      : importance === "medium"
        ? "-right-6 -top-6 h-24 w-24 blur-2xl"
        : "-right-5 -top-5 h-20 w-20 blur-2xl";
  const outerGlow =
    importance === "high" && accent === "red"
      ? "shadow-[0_0_48px_-14px_rgba(248,113,113,0.22)]"
      : importance === "high" && accent === "blue"
        ? "shadow-[0_0_44px_-16px_rgba(59,130,246,0.18)]"
        : importance === "medium"
          ? "shadow-[0_0_34px_-20px_rgba(148,163,184,0.08)]"
          : "";
  const glowSecond =
    accent === "blue"
      ? "from-blue-400/8"
      : accent === "red"
        ? "from-red-400/8"
        : accent === "amber"
          ? "from-amber-400/8"
          : accent === "violet"
            ? "from-violet-400/8"
            : "from-emerald-400/8";
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-900/40 p-5 ring-1 transition-shadow duration-500 ${ring} ${outerGlow}`}
    >
      <div
        className={`pointer-events-none absolute rounded-full bg-gradient-to-br ${glow} to-transparent ${orbMain} ${ambient}`}
      />
      <div
        className={`pointer-events-none absolute -bottom-6 -left-5 h-16 w-16 rounded-full bg-gradient-to-tr ${glowSecond} to-transparent blur-2xl analytics-ambient-subtle opacity-80`}
        style={{ animationDelay: "-4s" }}
      />
      <div className="relative flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-zinc-300 ring-1 ring-white/10">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500">{label}</p>
          <p className="mt-1 font-mono text-2xl font-semibold tabular-nums tracking-tight text-white">{value}</p>
          {sub ? <p className="mt-0.5 text-[11px] text-zinc-500">{sub}</p> : null}
        </div>
      </div>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
  className = "",
  importance = "medium",
  tone = "blue",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  importance?: "high" | "medium" | "low";
  tone?: "blue" | "violet" | "cyan" | "rose" | "amber";
}) {
  const ambient =
    importance === "high"
      ? "analytics-ambient-strong"
      : importance === "medium"
        ? "analytics-ambient"
        : "analytics-ambient-subtle";
  const fromTone =
    tone === "blue"
      ? "from-blue-500/14"
      : tone === "violet"
        ? "from-violet-500/14"
        : tone === "cyan"
          ? "from-cyan-500/15"
          : tone === "rose"
            ? "from-rose-500/14"
            : "from-amber-500/12";
  const fromToneSoft =
    tone === "blue"
      ? "from-blue-400/8"
      : tone === "violet"
        ? "from-violet-400/8"
        : tone === "cyan"
          ? "from-cyan-400/8"
          : tone === "rose"
            ? "from-rose-400/8"
            : "from-amber-400/8";
  const orbSize =
    importance === "high"
      ? "-right-12 -top-12 h-56 w-56 blur-3xl"
      : importance === "medium"
        ? "-right-10 -top-10 h-44 w-44 blur-3xl"
        : "-right-8 -top-8 h-36 w-36 blur-2xl";
  const panelShadow =
    importance === "high"
      ? tone === "rose"
        ? "shadow-[0_0_56px_-18px_rgba(251,113,133,0.14)]"
        : tone === "cyan"
          ? "shadow-[0_0_56px_-18px_rgba(34,211,238,0.12)]"
          : "shadow-[0_0_48px_-20px_rgba(59,130,246,0.12)]"
      : importance === "medium"
        ? "shadow-[0_0_40px_-22px_rgba(59,130,246,0.06)]"
        : "";
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-900/35 p-5 ring-1 ring-white/[0.04] transition-shadow duration-500 ${panelShadow} ${className}`}
    >
      <div
        className={`pointer-events-none absolute rounded-full bg-gradient-to-br ${fromTone} to-transparent ${orbSize} ${ambient}`}
      />
      <div
        className={`pointer-events-none absolute -bottom-10 -left-10 h-36 w-36 rounded-full bg-gradient-to-tr ${fromToneSoft} to-transparent blur-3xl analytics-ambient-subtle opacity-70`}
        style={{ animationDelay: "-5s" }}
      />
      <div className="relative mb-4">
        <h2 className="text-[13px] font-semibold tracking-tight text-white">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-[12px] text-zinc-500">{subtitle}</p> : null}
      </div>
      <div className="relative">{children}</div>
    </div>
  );
}

function aggregateAlerts(alerts: AlertCatalogItem[]) {
  const sev: Record<string, number> = {};
  const byAttack: Record<string, number> = {};
  const byDay: Record<string, number> = {};
  const confVals: number[] = [];
  const detTimes: number[] = [];

  for (const a of alerts) {
    const s = normSeverity(a.severity);
    sev[s] = (sev[s] || 0) + 1;
    const atk = attackLabel(a);
    byAttack[atk] = (byAttack[atk] || 0) + 1;
    const dk = dayKeyFromIso(a.detection?.attack_start_time);
    if (dk) byDay[dk] = (byDay[dk] || 0) + 1;
    const c = a.confidence?.severity;
    if (typeof c === "number" && !Number.isNaN(c)) confVals.push(c);
    const dt = a.detection_time_seconds;
    if (typeof dt === "number" && !Number.isNaN(dt)) detTimes.push(dt);
  }

  const pieRows = PIE_ORDER.map((name) => {
    const v = sev[name] ?? 0;
    if (v === 0) return null;
    return {
      name: name === "autre" ? "Autre" : name.charAt(0).toUpperCase() + name.slice(1),
      value: v,
      key: name,
      fill: SEVERITY_COLORS[name] || "#52525b",
    };
  }).filter(Boolean) as { name: string; value: number; key: string; fill: string }[];

  const attackRows = Object.entries(byAttack)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);

  const dayRows = Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, count]) => ({ day: day.slice(5), full: day, count }));

  const avgConf = confVals.length ? confVals.reduce((x, y) => x + y, 0) / confVals.length : null;
  const avgDet = detTimes.length ? detTimes.reduce((x, y) => x + y, 0) / detTimes.length : null;

  return {
    pieRows,
    attackRows,
    dayRows,
    avgConf,
    avgDet,
    distinctAttackTypes: Object.keys(byAttack).length,
    highPlus: (sev.critical || 0) + (sev.high || 0),
  };
}

export default function AlertsAnalyticsTab() {
  const [data, setData] = useState<AlertsCatalogResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const d = await fetchAllAlerts();
      setData(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erreur de chargement");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const agg = useMemo(() => {
    if (!data?.alerts?.length) return null;
    return aggregateAlerts(data.alerts);
  }, [data]);

  if (loading && !data) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-zinc-500">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500/80" aria-hidden />
        <p className="text-sm">Chargement du catalogue d’alertes…</p>
      </div>
    );
  }

  if (err && !data) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-6 text-red-200">
        <p className="font-medium">Impossible de charger les alertes.</p>
        <p className="mt-2 text-sm text-red-300/80">{err}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-400/40 px-3 py-2 text-sm text-red-100 hover:bg-red-950/40"
        >
          <RefreshCw size={16} /> Réessayer
        </button>
      </div>
    );
  }

  if (!data?.alerts?.length || !agg) {
    return (
      <p className="text-center text-sm text-zinc-500">
        Aucune alerte dans le catalogue.
      </p>
    );
  }

  const { alerts, count, source_path: sourcePath } = data;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-lg bg-cyan-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-cyan-200 ring-1 ring-cyan-400/30">
            Catalogue alertes
          </span>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-[12px] font-medium text-zinc-300 transition hover:border-blue-500/30 hover:text-white"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} aria-hidden />
            Actualiser
          </button>
        </div>
      </div>

      {sourcePath ? (
        <p className="text-[12px] text-zinc-500">
          Source : <code className="rounded bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[11px] text-zinc-400">{sourcePath}</code>
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi
          icon={<Bell size={20} aria-hidden />}
          label="Total alertes"
          value={formatInt(count)}
          sub="Jeu de données courant"
          accent="blue"
          importance="high"
        />
        <Kpi
          icon={<Skull size={20} className="text-red-400/90" aria-hidden />}
          label="Critique + élevé"
          value={formatInt(agg.highPlus)}
          sub="Sévérités critical & high"
          accent="red"
          importance="high"
        />
        <Kpi
          icon={<Target size={20} className="text-amber-400/90" aria-hidden />}
          label="Types d’attaque"
          value={formatInt(agg.distinctAttackTypes)}
          sub="Profiles distincts"
          accent="amber"
          importance="medium"
        />
        <Kpi
          icon={<Gauge size={20} className="text-violet-400/90" aria-hidden />}
          label="Confiance (sévérité)"
          value={agg.avgConf != null ? formatPct(agg.avgConf * 100) + " %" : "—"}
          sub="Moyenne du champ confidence.severity"
          accent="violet"
          importance="medium"
        />
        <Kpi
          icon={<Timer size={20} className="text-emerald-400/90" aria-hidden />}
          label="Délai pipeline"
          value={agg.avgDet != null ? formatInt(agg.avgDet) + " s" : "—"}
          sub="Moyenne detection_time_seconds"
          accent="emerald"
          importance="low"
        />
        <Kpi
          icon={<Shield size={20} aria-hidden />}
          label="Échantillon"
          value={formatInt(alerts.length)}
          sub="Entrées renvoyées par l’API"
          accent="blue"
          importance="low"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Répartition par sévérité"
          subtitle="Distribution des niveaux dans le catalogue"
          importance="high"
          tone="rose"
        >
          {agg.pieRows.length === 0 ? (
            <p className="text-sm text-zinc-500">Aucune donnée.</p>
          ) : (
            <div className="h-[280px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={agg.pieRows}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={88}
                    paddingAngle={2}
                    label={({ name, percent }) => `${name} ${(((percent ?? 0) * 100)).toFixed(0)}%`}
                  >
                    {agg.pieRows.map((e) => (
                      <Cell key={e.key} fill={e.fill} stroke="rgba(0,0,0,0.35)" />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(v) => [formatInt(typeof v === "number" ? v : Number(v)), "Alertes"]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Top types d’attaque" subtitle="Par attack_type / challenge_id (top 12)">
          {agg.attackRows.length === 0 ? (
            <p className="text-sm text-zinc-500">Aucune donnée.</p>
          ) : (
            <div className="h-[280px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agg.attackRows} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" horizontal={false} />
                  <XAxis type="number" stroke="#71717a" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="key"
                    width={120}
                    stroke="#71717a"
                    tick={{ fill: "#a1a1aa", fontSize: 10 }}
                    tickFormatter={(v: string) => (v.length > 18 ? `${v.slice(0, 16)}…` : v)}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(v) => [formatInt(typeof v === "number" ? v : Number(v)), "Alertes"]}
                    labelFormatter={(l) => (l == null ? "" : String(l))}
                  />
                  <Bar dataKey="count" name="Alertes" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title="Nombre d’alertes dans le temps"
        subtitle="Ligne + aire : agrégation par jour UTC (detection.attack_start_time), ordre chronologique"
        importance="high"
        tone="cyan"
      >
        {agg.dayRows.length === 0 ? (
          <p className="text-sm text-zinc-500">Pas de timestamps exploitables pour une série temporelle.</p>
        ) : (
          <div className="h-[320px] w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={agg.dayRows} margin={{ top: 8, left: 4, right: 12, bottom: 4 }}>
                <defs>
                  <linearGradient id="alertsTimeFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  dataKey="day"
                  stroke="#71717a"
                  tick={{ fill: "#a1a1aa", fontSize: 10 }}
                  tickMargin={6}
                />
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
                      const row = agg.dayRows.find((d) => d.day === label);
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
                  fill="url(#alertsTimeFill)"
                  dot={{ fill: "#38bdf8", strokeWidth: 0, r: 4 }}
                  activeDot={{ r: 6, fill: "#7dd3fc" }}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
    </div>
  );
}
