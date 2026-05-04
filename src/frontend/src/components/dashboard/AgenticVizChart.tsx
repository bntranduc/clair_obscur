"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type AgenticChartRow = { name: string; value: number | null };

export type AgenticToolChartPayload = {
  kind: "bar" | "line" | "histogram" | "pie";
  title: string;
  subtitle?: string | null;
  xLabel: string;
  yLabel: string;
  /** Pour les courbes : `null` = pas de mesure sur cette ligne (ligne conservée pour l’ordre). */
  data: AgenticChartRow[];
  kpis?: { label: string; value: string }[];
};

const BAR_COLORS = ["#3b82f6", "#a855f7", "#f97316", "#22c55e", "#eab308", "#ec4899", "#06b6d4"];

const TOOLTIP_STYLE = {
  borderRadius: 8,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(9,9,11,0.95)",
  padding: "8px 12px",
  fontSize: 12,
  color: "#e4e4e7",
  boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
};

function formatTick(v: string): string {
  const s = String(v);
  return s.length > 14 ? `${s.slice(0, 12)}…` : s;
}

function coerceChartScalar(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v.trim());
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function parseAgenticChartPayload(meta: unknown): AgenticToolChartPayload | null {
  if (!meta || typeof meta !== "object") return null;
  const m = meta as Record<string, unknown>;
  const chart = m.chart;
  if (!chart || typeof chart !== "object" || Array.isArray(chart)) return null;
  const c = chart as Record<string, unknown>;
  const kind = c.kind;
  if (kind !== "bar" && kind !== "line" && kind !== "histogram" && kind !== "pie") return null;
  if (typeof c.title !== "string") return null;
  if (typeof c.xLabel !== "string" || typeof c.yLabel !== "string") return null;
  if (!Array.isArray(c.data) || c.data.length === 0) return null;
  const data: AgenticChartRow[] = [];
  for (const row of c.data) {
    if (!row || typeof row !== "object") continue;
    const r = row as Record<string, unknown>;
    if (typeof r.name !== "string") continue;
    const val = coerceChartScalar(r.value);
    if (kind === "line") {
      data.push({ name: r.name, value: val });
    } else if (val !== null) {
      data.push({ name: r.name, value: val });
    }
  }
  if (data.length === 0) return null;
  if (kind === "line" && !data.some((d) => d.value !== null)) return null;

  let kpis: AgenticToolChartPayload["kpis"];
  if (Array.isArray(c.kpis)) {
    kpis = [];
    for (const k of c.kpis) {
      if (!k || typeof k !== "object") continue;
      const o = k as Record<string, unknown>;
      if (typeof o.label === "string" && typeof o.value === "string") kpis.push({ label: o.label, value: o.value });
    }
  }

  return {
    kind,
    title: c.title,
    subtitle: typeof c.subtitle === "string" ? c.subtitle : null,
    xLabel: c.xLabel,
    yLabel: c.yLabel,
    data,
    kpis,
  };
}

export function AgenticVizChart({ payload }: { payload: AgenticToolChartPayload }) {
  const longTicks = payload.data.some((d) => d.name.length > 10);
  const angle = longTicks ? -32 : 0;
  const barData =
    payload.kind === "line"
      ? payload.data
      : payload.data.filter((d): d is { name: string; value: number } => d.value !== null);
  const pieShowLabels = payload.kind === "pie" && barData.length > 0 && barData.length <= 10;

  return (
    <div className="rounded-xl border border-cyan-500/25 bg-gradient-to-b from-zinc-900/80 to-black/40 overflow-hidden">
      <div className="px-4 pt-4 pb-2 border-b border-white/[0.06]">
        <h4 className="text-sm font-semibold text-white tracking-tight">{payload.title}</h4>
        {payload.subtitle ? <p className="text-xs text-zinc-500 mt-1">{payload.subtitle}</p> : null}
      </div>

      {payload.kpis && payload.kpis.length > 0 ? (
        <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-3 gap-2 border-b border-white/[0.06]">
          {payload.kpis.map((k, i) => (
            <div
              key={`${k.label}-${i}`}
              className="rounded-lg bg-white/[0.04] border border-white/[0.06] px-3 py-2"
            >
              <p className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">{k.label}</p>
              <p className="text-sm font-mono text-cyan-100/95 tabular-nums mt-0.5 truncate" title={k.value}>
                {k.value}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <div
        className={
          payload.kind === "pie"
            ? "p-4 h-[min(360px,52vh)] min-h-[300px] w-full min-w-0"
            : "p-4 h-[280px] w-full min-w-0"
        }
      >
        <ResponsiveContainer width="100%" height="100%">
          {payload.kind === "line" ? (
            <LineChart data={payload.data} margin={{ top: 8, right: 12, left: 0, bottom: longTicks ? 48 : 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="name"
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickFormatter={formatTick}
                angle={angle}
                textAnchor={longTicks ? "end" : "middle"}
                height={longTicks ? 56 : 28}
                label={{ value: payload.xLabel, position: "insideBottom", offset: longTicks ? -36 : -4, fill: "#a1a1aa", fontSize: 11 }}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 10 }}
                label={{ value: payload.yLabel, angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 11 }}
              />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#38bdf8"
                strokeWidth={2}
                connectNulls={false}
                dot={{ r: 3, fill: "#38bdf8" }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          ) : payload.kind === "pie" ? (
            <PieChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <Pie
                data={barData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={52}
                outerRadius={96}
                paddingAngle={2}
                stroke="rgba(0,0,0,0.35)"
                strokeWidth={1}
                label={
                  pieShowLabels
                    ? ({ name, percent }) =>
                        `${formatTick(String(name))} ${percent !== undefined ? (percent * 100).toFixed(0) : ""}%`
                    : false
                }
              >
                {barData.map((_, i) => (
                  <Cell key={`pie-${i}`} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(value, _name, item) => {
                  const v = typeof value === "number" ? value : Number(value);
                  const pl = item?.payload as { name?: string } | undefined;
                  const nm = pl?.name != null ? String(pl.name) : "";
                  return [
                    Number.isFinite(v) ? v.toLocaleString("fr-FR") : String(value ?? ""),
                    nm || payload.yLabel,
                  ];
                }}
              />
              <Legend
                verticalAlign="bottom"
                layout="horizontal"
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value) => <span className="text-zinc-400">{formatTick(String(value))}</span>}
              />
            </PieChart>
          ) : (
            <BarChart data={barData} margin={{ top: 8, right: 12, left: 0, bottom: longTicks ? 52 : 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="name"
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickFormatter={formatTick}
                angle={angle}
                textAnchor={longTicks ? "end" : "middle"}
                height={longTicks ? 60 : 32}
                interval={0}
                label={{ value: payload.xLabel, position: "insideBottom", offset: longTicks ? -40 : -4, fill: "#a1a1aa", fontSize: 11 }}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 10 }}
                label={{ value: payload.yLabel, angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 11 }}
              />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={48}>
                {barData.map((_, i) => (
                  <Cell key={`cell-${i}`} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <p className="px-4 pb-3 text-[10px] text-zinc-600">
        Graphique dynamique (Recharts : barres, ligne, histogramme, camembert) — même famille que l’onglet Analytics.
      </p>
    </div>
  );
}
