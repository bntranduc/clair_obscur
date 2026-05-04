"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CalendarRange,
  Database,
  LayoutDashboard,
  LineChart,
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
import { fetchDynamodbAnalytics, fetchSiemAnalytics } from "@/lib/api";
import type { SiemDashboard, SiemGeoLogPoint, SiemKeyCount } from "@/types/siemAnalytics";

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

function formatAnalyticsRange(sinceIso: string, untilIso: string): string {
  try {
    const df = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" });
    return `${df.format(new Date(sinceIso))} → ${df.format(new Date(untilIso))}`;
  } catch {
    return `${sinceIso} → ${untilIso}`;
  }
}

/** Valeur ``datetime-local`` (fuseau navigateur) → ISO UTC pour l’API. */
function datetimeLocalToIsoUtc(value: string): string | null {
  const t = value.trim();
  if (!t) return null;
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
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
  if (!rows.length) {
    return <p className="text-sm text-zinc-500">Aucune donnée pour cette série.</p>;
  }
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

function DataSourceBadge({ data }: { data: SiemDashboard }) {
  if (data.data_source === "demo") {
    return (
      <span className="rounded-lg bg-amber-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-200 ring-1 ring-amber-400/30">
        Données de démonstration
      </span>
    );
  }
  if (data.data_source === "dynamodb") {
    return (
      <span className="rounded-lg bg-violet-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-violet-200 ring-1 ring-violet-400/30">
        DynamoDB
      </span>
    );
  }
  return (
    <span className="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-200 ring-1 ring-emerald-400/25">
      OpenSearch
    </span>
  );
}

function SiemDashboardView({
  data,
  onRefresh,
  refreshing,
}: {
  data: SiemDashboard;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const gradId = `siemArea-${data.data_source}`;
  const timelineChart =
    data.timeline.length > 0
      ? data.timeline.map((p) => ({
          label: formatHourLabel(p.t),
          count: p.count,
        }))
      : [{ label: "—", count: 0 }];

  const geoLogs: SiemGeoLogPoint[] = data.geo_logs ?? EMPTY_GEO_LOGS;
  const isDynamo = data.data_source === "dynamodb";
  const fixedRange =
    typeof data.time_filter_since === "string" &&
    data.time_filter_since.length > 0 &&
    typeof data.time_filter_until === "string" &&
    data.time_filter_until.length > 0;
  const rangeLine = fixedRange ? formatAnalyticsRange(data.time_filter_since!, data.time_filter_until!) : null;
  const volumeSub = isDynamo
    ? `${data.dynamodb_items_scanned?.toLocaleString("fr-FR") ?? formatInt(data.total_events)} évén. lus${
        rangeLine ? ` · ${rangeLine}` : " · partition courte"
      }`
    : rangeLine
      ? `Plage : ${rangeLine}`
      : `${data.time_range_hours} h glissantes`;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <DataSourceBadge data={data} />
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-[12px] font-medium text-zinc-300 transition hover:border-blue-500/30 hover:text-white"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} aria-hidden />
            Actualiser
          </button>
        </div>
      </div>

      {isDynamo && data.dynamodb_pk ? (
        <p className="text-[12px] leading-relaxed text-zinc-500">
          Partition{" "}
          <code className="rounded bg-zinc-800/90 px-1.5 py-0.5 font-mono text-[11px] text-zinc-300">
            {data.dynamodb_pk}
          </code>
          {data.dynamodb_truncated ? (
            <span className="text-amber-400/90"> · échantillon tronqué (limite max_items)</span>
          ) : null}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          icon={<Activity size={20} />}
          label="Volume (échantillon)"
          value={formatInt(data.total_events)}
          sub={volumeSub}
          accent="blue"
        />
        <KpiCard
          icon={<Radio size={20} />}
          label="Débit moyen"
          value={data.events_per_minute_avg.toFixed(2)}
          sub="événements / minute (sur plage horodatage des logs lus)"
          accent="red"
        />
        <KpiCard
          icon={<Users size={20} />}
          label="Sources IP distinctes"
          value={formatInt(data.unique_source_ips)}
          sub="dans l’échantillon"
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
        subtitle={
          isDynamo
            ? "Histogramme par heure (agrégation en mémoire sur l’échantillon DynamoDB)"
            : "Histogramme par heure — corrélation incidents et charge"
        }
        className="min-h-[320px]"
      >
        <div className="h-[280px] w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timelineChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
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
              <YAxis tick={{ fill: "#71717a", fontSize: 10 }} tickLine={false} axisLine={false} width={44} />
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
                fill={`url(#${gradId})`}
                animationDuration={600}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Sources de logs" subtitle="Répartition par type (application, auth, réseau, système)">
          {data.log_sources.length === 0 ? (
            <p className="py-8 text-center text-sm text-zinc-500">Aucun événement dans l’échantillon.</p>
          ) : (
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
          )}
        </Panel>

        <Panel title="Protocoles (flux réseau)" subtitle="Distribution sur les journaux réseau de l’échantillon">
          <div className="h-[260px] w-full min-w-0">
            {data.protocols.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-zinc-500">Aucun flux réseau.</div>
            ) : (
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
            )}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Actions pare-feu" subtitle="Accept / reject / drop (logs réseau)">
          <HorizontalBars rows={data.network_actions} color="#3b82f6" />
        </Panel>
        <Panel title="Authentification" subtitle="Succès vs échecs (logs auth)">
          <HorizontalBars rows={data.auth_by_status} color="#4ade80" />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Principales adresses source" subtitle="Top IP dans l’échantillon">
          <ul className="space-y-2">
            {data.top_source_ips.length === 0 ? (
              <li className="text-sm text-zinc-500">Aucune IP source.</li>
            ) : (
              data.top_source_ips.map((row) => (
                <li
                  key={row.ip}
                  className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2 font-mono text-[12px]"
                >
                  <span className="truncate text-blue-200/90">{row.ip}</span>
                  <span className="shrink-0 tabular-nums text-zinc-400">{formatInt(row.count)}</span>
                </li>
              ))
            )}
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
        subtitle={`${geoLogs.length.toLocaleString("fr-FR")} point(s) avec lat/lon dans l’échantillon`}
        className="min-h-[420px]"
      >
        <div className="mb-3 flex items-center gap-2 text-[12px] text-zinc-500">
          <MapPin size={14} className="shrink-0 text-blue-400/90" aria-hidden />
          <span>Fond OpenStreetMap — survol pour détail.</span>
        </div>
        <div className="relative">
          <SiemGeoMap points={geoLogs} />
          {geoLogs.length === 0 ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-lg bg-zinc-950/55 px-4">
              <p className="max-w-md rounded-lg border border-white/10 bg-zinc-900/90 px-4 py-3 text-center text-sm text-zinc-300 shadow-lg">
                Aucun log avec <code className="text-zinc-400">geolocation_lat</code> et{" "}
                <code className="text-zinc-400">geolocation_lon</code> dans l’échantillon.
              </p>
            </div>
          ) : null}
        </div>
      </Panel>

      <p className="flex items-center justify-center gap-2 text-center text-[11px] text-zinc-600">
        <Network size={12} aria-hidden />
        {isDynamo
          ? "Agrégations calculées côté API sur un échantillon DynamoDB (Query par pk, tronqué à max_items)."
          : "Agrégations OpenSearch — rafraîchissement automatique 30 s."}
      </p>
    </div>
  );
}

type TabId = "general" | "siem";

export default function SiemAnalyticsDashboard() {
  const [tab, setTab] = useState<TabId>("general");
  const [siemData, setSiemData] = useState<SiemDashboard | null>(null);
  const [dynamoData, setDynamoData] = useState<SiemDashboard | null>(null);
  const [siemErr, setSiemErr] = useState<string | null>(null);
  const [dynamoErr, setDynamoErr] = useState<string | null>(null);
  const [loadingSiem, setLoadingSiem] = useState(false);
  const [loadingDynamo, setLoadingDynamo] = useState(false);
  const [rangeIso, setRangeIso] = useState<{ since: string; until: string } | null>(null);
  const [sinceInput, setSinceInput] = useState("");
  const [untilInput, setUntilInput] = useState("");
  const [timeFilterErr, setTimeFilterErr] = useState<string | null>(null);

  const loadSiem = useCallback(async () => {
    setSiemErr(null);
    setLoadingSiem(true);
    try {
      const d = await fetchSiemAnalytics(
        24,
        rangeIso ? { since: rangeIso.since, until: rangeIso.until } : undefined,
      );
      setSiemData(d);
    } catch (e) {
      setSiemErr(e instanceof Error ? e.message : "Erreur de chargement");
      setSiemData(null);
    } finally {
      setLoadingSiem(false);
    }
  }, [rangeIso]);

  const loadDynamo = useCallback(async () => {
    setDynamoErr(null);
    setLoadingDynamo(true);
    try {
      const d = await fetchDynamodbAnalytics(
        8000,
        rangeIso ? { since: rangeIso.since, until: rangeIso.until } : undefined,
      );
      setDynamoData(d);
    } catch (e) {
      setDynamoErr(e instanceof Error ? e.message : "Erreur de chargement");
      setDynamoData(null);
    } finally {
      setLoadingDynamo(false);
    }
  }, [rangeIso]);

  useEffect(() => {
    void loadDynamo();
  }, [loadDynamo]);

  useEffect(() => {
    void loadSiem();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") void loadSiem();
    }, 30_000);
    return () => clearInterval(id);
  }, [loadSiem]);

  const activeLoading = tab === "general" ? loadingDynamo : loadingSiem;
  const activeError = tab === "general" ? dynamoErr : siemErr;
  const activeData = tab === "general" ? dynamoData : siemData;
  const activeLoad = tab === "general" ? loadDynamo : loadSiem;

  const applyTimeFilter = () => {
    setTimeFilterErr(null);
    const sIso = datetimeLocalToIsoUtc(sinceInput);
    const uIso = datetimeLocalToIsoUtc(untilInput);
    if (!sinceInput.trim() || !untilInput.trim()) {
      setTimeFilterErr("Renseignez la date et l’heure de début et de fin.");
      return;
    }
    if (!sIso || !uIso) {
      setTimeFilterErr("Dates invalides.");
      return;
    }
    if (new Date(sIso).getTime() > new Date(uIso).getTime()) {
      setTimeFilterErr("Le début doit être antérieur ou égal à la fin.");
      return;
    }
    setRangeIso({ since: sIso, until: uIso });
  };

  const resetTimeFilter = () => {
    setTimeFilterErr(null);
    setRangeIso(null);
    setSinceInput("");
    setUntilInput("");
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Analytics</h1>
          <p className="mt-1 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
            <strong className="font-medium text-zinc-300">Général</strong> : métriques et graphiques à partir d’un
            échantillon DynamoDB. <strong className="font-medium text-zinc-300">SIEM</strong> : vue OpenSearch
            24&nbsp;h (ou plage personnalisée ci‑dessous).
          </p>
        </div>
      </header>

      <section
        className="rounded-2xl border border-white/[0.08] bg-zinc-900/30 p-4 ring-1 ring-white/[0.04] sm:p-5"
        aria-label="Filtre par période"
      >
        <div className="mb-3 flex items-center gap-2 text-[12px] font-medium text-zinc-400">
          <CalendarRange size={16} className="shrink-0 text-blue-400/90" aria-hidden />
          Période (fuseau du navigateur)
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
          <label className="flex min-w-[200px] flex-1 flex-col gap-1.5 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
            Début
            <input
              type="datetime-local"
              value={sinceInput}
              onChange={(e) => setSinceInput(e.target.value)}
              className="rounded-xl border border-white/[0.1] bg-zinc-950/80 px-3 py-2 font-mono text-[13px] text-zinc-200 outline-none ring-0 focus:border-blue-500/40"
            />
          </label>
          <label className="flex min-w-[200px] flex-1 flex-col gap-1.5 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
            Fin
            <input
              type="datetime-local"
              value={untilInput}
              onChange={(e) => setUntilInput(e.target.value)}
              className="rounded-xl border border-white/[0.1] bg-zinc-950/80 px-3 py-2 font-mono text-[13px] text-zinc-200 outline-none ring-0 focus:border-blue-500/40"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void applyTimeFilter()}
              className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500"
            >
              Appliquer
            </button>
            <button
              type="button"
              onClick={() => {
                resetTimeFilter();
              }}
              className="inline-flex items-center justify-center rounded-xl border border-white/[0.12] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-white/20 hover:text-white"
            >
              Réinitialiser
            </button>
          </div>
        </div>
        {timeFilterErr ? <p className="mt-3 text-sm text-amber-400/95">{timeFilterErr}</p> : null}
        {rangeIso ? (
          <p className="mt-3 text-[12px] text-zinc-500">
            Filtre actif :{" "}
            <span className="font-mono text-zinc-400">{formatAnalyticsRange(rangeIso.since, rangeIso.until)}</span>
          </p>
        ) : (
          <p className="mt-3 text-[12px] text-zinc-600">
            Sans filtre : DynamoDB lit l’échantillon le plus récent ; SIEM utilise les 24&nbsp;h glissantes OpenSearch.
          </p>
        )}
      </section>

      <div className="flex flex-wrap gap-2 border-b border-white/[0.08] pb-1">
        <button
          type="button"
          onClick={() => setTab("general")}
          className={`inline-flex items-center gap-2 rounded-t-lg px-4 py-2.5 text-sm font-medium transition ${
            tab === "general"
              ? "bg-zinc-900 text-white ring-1 ring-white/10"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <LayoutDashboard size={16} aria-hidden />
          Général (DynamoDB)
        </button>
        <button
          type="button"
          onClick={() => setTab("siem")}
          className={`inline-flex items-center gap-2 rounded-t-lg px-4 py-2.5 text-sm font-medium transition ${
            tab === "siem" ? "bg-zinc-900 text-white ring-1 ring-white/10" : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <LineChart size={16} aria-hidden />
          SIEM (OpenSearch)
        </button>
      </div>

      {activeLoading && !activeData ? (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-zinc-500">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500/80" aria-hidden />
          <p className="text-sm">{tab === "general" ? "Chargement DynamoDB…" : "Chargement SIEM…"}</p>
        </div>
      ) : null}

      {activeError && !activeData ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-6 text-red-200">
          <p className="font-medium">Impossible de charger cet onglet.</p>
          <p className="mt-2 text-sm text-red-300/80">{activeError}</p>
          <button
            type="button"
            onClick={() => {
              void activeLoad();
            }}
            className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-400/40 px-3 py-2 text-sm text-red-100 hover:bg-red-950/40"
          >
            <RefreshCw size={16} /> Réessayer
          </button>
        </div>
      ) : null}

      {activeData ? <SiemDashboardView data={activeData} onRefresh={() => void activeLoad()} refreshing={activeLoading} /> : null}
    </div>
  );
}
