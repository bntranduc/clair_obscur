"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Database,
  Loader2,
  MapPin,
  Network,
  Radio,
  RefreshCw,
  Shield,
  Users,
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
import { fetchSiemAnalytics } from "@/lib/api";
import type { SiemDashboard, SiemGeoLogPoint, SiemKeyCount } from "@/types/siemAnalytics";

/** Référence stable pour « pas de points » (évite un nouveau [] à chaque rendu → boucle Leaflet). */
const EMPTY_GEO_LOGS: SiemGeoLogPoint[] = [];

const SiemGeoMap = dynamic(() => import("./SiemGeoMap").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex h-[380px] items-center justify-center rounded-lg border border-white/[0.08] bg-zinc-950/40 text-sm text-zinc-500">
      Chargement de la carte…
    </div>
  ),
});

const PIE_COLORS = ["#3b82f6", "#ef4444", "#fbbf24", "#4ade80", "#f97316", "#94a3b8"];
const TOOLTIP_STYLE = {
  borderRadius: 8,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(9,9,11,0.95)",
  padding: "8px 12px",
  fontSize: 12,
  color: "#e4e4e7",
  boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
};

function formatHourLabel(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(11, 16);
    return new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(d);
  } catch {
    return iso;
  }
}

function formatInt(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}

function KpiCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  accent: "blue" | "red" | "amber" | "emerald";
}) {
  const ring =
    accent === "blue"
      ? "ring-blue-500/20"
      : accent === "red"
        ? "ring-red-500/20"
        : accent === "amber"
          ? "ring-amber-500/20"
          : "ring-emerald-500/20";
  const glow =
    accent === "blue"
      ? "from-blue-500/10"
      : accent === "red"
        ? "from-red-500/10"
        : accent === "amber"
          ? "from-amber-500/10"
          : "from-emerald-500/10";
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-900/40 p-5 ring-1 ${ring}`}
    >
      <div className={`pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br ${glow} to-transparent blur-2xl`} />
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
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-white/[0.08] bg-zinc-900/35 p-5 ring-1 ring-white/[0.04] ${className}`}
    >
      <div className="mb-4">
        <h2 className="text-[13px] font-semibold tracking-tight text-white">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-[12px] text-zinc-500">{subtitle}</p> : null}
      </div>
      {children}
    </div>
  );
}

function HorizontalBars({ rows, color }: { rows: SiemKeyCount[]; color: string }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="mb-1 flex justify-between gap-2 text-[12px]">
            <span className="truncate font-mono text-zinc-300">{r.key}</span>
            <span className="shrink-0 tabular-nums text-zinc-500">{formatInt(r.count)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${(r.count / max) * 100}%`, backgroundColor: color }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function SiemAnalyticsDashboard() {
  const [data, setData] = useState<SiemDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await fetchSiemAnalytics(24);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const timelineChart = data?.timeline.map((p) => ({
    label: formatHourLabel(p.t),
    count: p.count,
  }));

  if (loading && !data) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-zinc-500">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500/80" aria-hidden />
        <p className="text-sm">Chargement des métriques SIEM…</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-6 text-red-200">
        <p className="font-medium">Impossible de joindre l’API analytics.</p>
        <p className="mt-2 text-sm text-red-300/80">{error}</p>
        <button
          type="button"
          onClick={() => {
            setLoading(true);
            load();
          }}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-400/40 px-3 py-2 text-sm text-red-100 hover:bg-red-950/40"
        >
          <RefreshCw size={16} /> Réessayer
        </button>
      </div>
    );
  }

  if (!data) return null;

  const geoLogs: SiemGeoLogPoint[] = data.geo_logs ?? EMPTY_GEO_LOGS;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Analytics SIEM</h1>
          <p className="mt-1 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
            Vue opérationnelle : volume d’événements, répartition par source, flux réseau et authentification.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {data.data_source === "demo" ? (
            <span className="rounded-lg bg-amber-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-200 ring-1 ring-amber-400/30">
              Données de démonstration
            </span>
          ) : (
            <span className="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-200 ring-1 ring-emerald-400/25">
              OpenSearch
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              load();
            }}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-[12px] font-medium text-zinc-300 transition hover:border-blue-500/30 hover:text-white"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} aria-hidden />
            Actualiser
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          icon={<Activity size={20} />}
          label="Volume (fenêtre)"
          value={formatInt(data.total_events)}
          sub={`${data.time_range_hours} h glissantes`}
          accent="blue"
        />
        <KpiCard
          icon={<Radio size={20} />}
          label="Débit moyen"
          value={data.events_per_minute_avg.toFixed(2)}
          sub="événements / minute"
          accent="red"
        />
        <KpiCard
          icon={<Users size={20} />}
          label="Sources IP distinctes"
          value={formatInt(data.unique_source_ips)}
          sub="dans la fenêtre"
          accent="amber"
        />
        <KpiCard
          icon={<Database size={20} />}
          label="Mise à jour"
          value={new Intl.DateTimeFormat("fr-FR", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }).format(new Date(data.generated_at))}
          sub="UTC"
          accent="emerald"
        />
      </div>

      <Panel
        title="Chronologie du volume"
        subtitle="Histogramme par heure — corrélation incidents et charge"
        className="min-h-[320px]"
      >
        <div className="h-[280px] w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timelineChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="siemArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <Tooltip
                contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(v) => [formatInt(Number(v ?? 0)), "Événements"]}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#siemArea)"
                animationDuration={600}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Sources de logs" subtitle="Répartition par type (application, auth, réseau, système)">
          <div className="mx-auto h-[260px] w-full max-w-md">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.log_sources as { key: string; count: number }[]}
                  dataKey="count"
                  nameKey="key"
                  cx="50%"
                  cy="50%"
                  innerRadius={58}
                  outerRadius={88}
                  paddingAngle={2}
                  animationDuration={600}
                >
                  {data.log_sources.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="rgba(0,0,0,0.3)" />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => formatInt(Number(v ?? 0))} />
                <Legend
                  wrapperStyle={{ fontSize: 11, paddingTop: 12 }}
                  formatter={(value) => <span className="text-zinc-400">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Protocoles (flux réseau)" subtitle="Distribution observée sur les journaux réseau">
          <div className="h-[260px] w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.protocols} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#71717a", fontSize: 10 }} />
                <YAxis
                  type="category"
                  dataKey="key"
                  width={56}
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
                  formatter={(v) => formatInt(Number(v ?? 0))}
                />
                <Bar dataKey="count" fill="#ef4444" radius={[0, 6, 6, 0]} animationDuration={600} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Actions pare-feu" subtitle="Accept / reject / drop sur les événements réseau">
          <HorizontalBars rows={data.network_actions} color="#3b82f6" />
        </Panel>
        <Panel title="Authentification" subtitle="Succès vs échecs (logs auth)">
          <HorizontalBars rows={data.auth_by_status} color="#4ade80" />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Principales adresses source" subtitle="Top IP émettrices sur la fenêtre">
          <ul className="space-y-2">
            {data.top_source_ips.map((row) => (
              <li
                key={row.ip}
                className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2 font-mono text-[12px]"
              >
                <span className="truncate text-blue-200/90">{row.ip}</span>
                <span className="shrink-0 tabular-nums text-zinc-400">{formatInt(row.count)}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Sévérité (logs système)" subtitle="info, notice, warning…">
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 h-5 w-5 shrink-0 text-zinc-500" aria-hidden />
            <HorizontalBars rows={data.system_by_severity} color="#fbbf24" />
          </div>
        </Panel>
      </div>

      <Panel
        title="Carte des logs géolocalisés"
        subtitle={`${geoLogs.length.toLocaleString("fr-FR")} événement(s) avec geolocation_lat / geolocation_lon sur la fenêtre`}
        className="min-h-[420px]"
      >
        <div className="mb-3 flex items-center gap-2 text-[12px] text-zinc-500">
          <MapPin size={14} className="shrink-0 text-blue-400/90" aria-hidden />
          <span>Fond OpenStreetMap — survol d’un point pour la source, l’IP et l’horodatage si présents.</span>
        </div>
        <div className="relative">
          <SiemGeoMap points={geoLogs} />
          {geoLogs.length === 0 ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-lg bg-zinc-950/55 px-4">
              <p className="max-w-md rounded-lg border border-white/10 bg-zinc-900/90 px-4 py-3 text-center text-sm text-zinc-300 shadow-lg">
                Aucun log avec <code className="text-zinc-400">geolocation_lat</code> et{" "}
                <code className="text-zinc-400">geolocation_lon</code> sur cette période — carte vide (vue monde).
              </p>
            </div>
          ) : null}
        </div>
      </Panel>

      <p className="flex items-center justify-center gap-2 text-center text-[11px] text-zinc-600">
        <Network size={12} aria-hidden />
        Agrégations alignées sur un index normalisé type SIEM — rafraîchissement automatique 30 s.
      </p>
    </div>
  );
}
