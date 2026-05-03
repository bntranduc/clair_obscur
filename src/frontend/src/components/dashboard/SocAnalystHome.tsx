"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  Bot,
  ClipboardList,
  LayoutDashboard,
  Radio,
  Search,
  ShieldAlert,
  Sparkles,
  Ticket,
  Zap,
} from "lucide-react";
import { fetchSiemAnalytics } from "@/lib/api";
import type { SiemDashboard } from "@/types/siemAnalytics";

function formatFrDate(d: Date): string {
  return d.toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatFrTime(d: Date): string {
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

const quickLinks: {
  href: string;
  label: string;
  hint: string;
  icon: ReactNode;
  accent: string;
}[] = [
  {
    href: "/dashboard/logs",
    label: "Logs normalisés",
    hint: "Recherche & corrélation sur le brut S3",
    icon: <Search size={22} strokeWidth={1.75} />,
    accent: "from-sky-500/25 to-blue-600/10 ring-sky-500/20",
  },
  {
    href: "/dashboard/analytics",
    label: "Analytics SIEM",
    hint: "Volume, IP sources, timeline 24 h",
    icon: <LayoutDashboard size={22} strokeWidth={1.75} />,
    accent: "from-violet-500/25 to-indigo-600/10 ring-violet-500/20",
  },
  {
    href: "/dashboard/alertes",
    label: "File d’alertes",
    hint: "Triage & fiches incidents modèle",
    icon: <ShieldAlert size={22} strokeWidth={1.75} />,
    accent: "from-rose-500/25 to-red-600/10 ring-rose-500/20",
  },
  {
    href: "/dashboard/network",
    label: "Carte réseau",
    hint: "Vue topologique & flux",
    icon: <Activity size={22} strokeWidth={1.75} />,
    accent: "from-emerald-500/20 to-teal-600/10 ring-emerald-500/20",
  },
  {
    href: "/dashboard/tickets",
    label: "Tickets",
    hint: "Suivi escalade & post-mortem",
    icon: <Ticket size={22} strokeWidth={1.75} />,
    accent: "from-amber-500/20 to-orange-600/10 ring-amber-500/20",
  },
  {
    href: "/dashboard/chat",
    label: "Assistant IA",
    hint: "Synthèse & questions sur les logs",
    icon: <Bot size={22} strokeWidth={1.75} />,
    accent: "from-cyan-500/20 to-blue-600/10 ring-cyan-500/20",
  },
];

const shiftFocus = [
  {
    title: "Triage critique",
    text: "Prioriser sévérité haute et échecs d’authentification avant élargissement.",
    icon: <Zap size={18} strokeWidth={2} className="text-amber-400" />,
  },
  {
    title: "Fenêtre d’observation",
    text: "Aligner timeline SIEM et logs normalisés sur le même fuseau (UTC / local).",
    icon: <Radio size={18} strokeWidth={2} className="text-sky-400" />,
  },
  {
    title: "Chaîne de preuve",
    text: "Conserver raw_ref (S3, ligne) pour toute escalade ou rapport.",
    icon: <ClipboardList size={18} strokeWidth={2} className="text-zinc-300" />,
  },
  {
    title: "Playbooks & wiki",
    text: "Vérifier procédures d’investigation avant actions destructrices.",
    icon: <Sparkles size={18} strokeWidth={2} className="text-violet-400" />,
  },
];

export default function SocAnalystHome() {
  const [now, setNow] = useState<Date | null>(null);
  const [siem, setSiem] = useState<SiemDashboard | null>(null);
  const [siemError, setSiemError] = useState<string | null>(null);
  const [siemLoading, setSiemLoading] = useState(true);

  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setSiemLoading(true);
        setSiemError(null);
        const d = await fetchSiemAnalytics(24);
        if (!cancelled) setSiem(d);
      } catch (e) {
        if (!cancelled)
          setSiemError(e instanceof Error ? e.message : "Indisponible");
      } finally {
        if (!cancelled) setSiemLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const timelineBars = useMemo(() => {
    if (!siem?.timeline?.length) return [];
    const slice = siem.timeline.slice(-16);
    const max = Math.max(1, ...slice.map((p) => p.count));
    return slice.map((p) => ({ ...p, h: Math.round((p.count / max) * 100) }));
  }, [siem]);

  const displayDate = now ?? new Date();

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 pb-4">
      {/* Hero */}
      <header className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-br from-zinc-900/90 via-zinc-950/95 to-zinc-950 p-8 shadow-[0_0_0_1px_rgba(255,255,255,0.04)_inset] sm:p-10">
        <div
          className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-blue-500/12 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-red-500/10 blur-3xl"
          aria-hidden
        />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-400/90">Poste analyste SOC</p>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Centre d’opérations
            </h1>
            <p className="max-w-xl text-[15px] leading-relaxed text-zinc-400">
              Vue d’ensemble pour démarrer un shift : indicateurs SIEM 24 h, accès rapides et rappels d’investigation.
            </p>
          </div>
          <div className="flex flex-col items-start gap-1 rounded-xl border border-white/[0.08] bg-black/25 px-5 py-4 text-left lg:items-end lg:text-right">
            <span className="text-[13px] capitalize text-zinc-300">{formatFrDate(displayDate)}</span>
            <span className="font-mono text-2xl font-medium tabular-nums tracking-tight text-white">
              {formatFrTime(displayDate)}
            </span>
            <span className="text-[11px] text-zinc-500">Heure locale navigateur</span>
          </div>
        </div>
      </header>

      {/* KPIs */}
      <section aria-labelledby="soc-kpi-heading">
        <div className="mb-4 flex items-end justify-between gap-4">
          <h2 id="soc-kpi-heading" className="text-lg font-semibold text-white">
            Indicateurs 24 h
          </h2>
          {siem && (
            <span
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${
                siem.data_source === "opensearch"
                  ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/25"
                  : "bg-amber-500/15 text-amber-200 ring-1 ring-amber-500/25"
              }`}
            >
              {siem.data_source === "opensearch" ? "OpenSearch" : "Démo"}
            </span>
          )}
        </div>
        {siemError && (
          <p className="mb-4 rounded-lg border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
            SIEM : {siemError}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: "Événements",
              value: siemLoading ? "—" : siem ? siem.total_events.toLocaleString("fr-FR") : "—",
              sub: "fenêtre glissante",
            },
            {
              label: "Débit moyen",
              value: siemLoading ? "—" : siem ? `${siem.events_per_minute_avg.toFixed(1)} / min` : "—",
              sub: "lissé sur 24 h",
            },
            {
              label: "IP sources uniques",
              value: siemLoading ? "—" : siem ? siem.unique_source_ips.toLocaleString("fr-FR") : "—",
              sub: "périphérie observée",
            },
            {
              label: "Rafraîchissement",
              value: siemLoading ? "…" : siem ? new Date(siem.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "—",
              sub: "côté API",
            },
          ].map((k) => (
            <div
              key={k.label}
              className="rounded-xl border border-white/[0.07] bg-zinc-900/40 px-5 py-5 ring-1 ring-inset ring-white/[0.03] backdrop-blur-sm transition hover:border-white/[0.1]"
            >
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-zinc-500">{k.label}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight text-white">{k.value}</p>
              <p className="mt-1 text-[12px] text-zinc-500">{k.sub}</p>
            </div>
          ))}
        </div>

        {timelineBars.length > 0 && (
          <div className="mt-5 rounded-xl border border-white/[0.06] bg-zinc-950/50 px-4 py-4">
            <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">Activité récente</p>
            <div className="flex h-14 items-end justify-between gap-0.5 sm:gap-1">
              {timelineBars.map((p, i) => (
                <div
                  key={`${p.t}-${i}`}
                  className="min-w-0 flex-1 rounded-t-sm bg-gradient-to-t from-blue-600/50 to-sky-400/85 opacity-90 transition hover:opacity-100"
                  style={{ height: `${Math.max(8, p.h)}%` }}
                  title={`${p.t}: ${p.count}`}
                />
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Quick links */}
      <section aria-labelledby="soc-quick-heading">
        <h2 id="soc-quick-heading" className="mb-4 text-lg font-semibold text-white">
          Accès rapides
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {quickLinks.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`group relative overflow-hidden rounded-xl border border-white/[0.07] bg-gradient-to-br ${item.accent} p-5 ring-1 ring-inset ring-white/[0.04] transition hover:border-white/[0.12] hover:ring-white/[0.08]`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-black/30 text-zinc-100 ring-1 ring-white/10">
                  {item.icon}
                </span>
                <ArrowRight
                  size={18}
                  className="shrink-0 text-zinc-500 transition group-hover:translate-x-0.5 group-hover:text-zinc-300"
                  aria-hidden
                />
              </div>
              <h3 className="mt-4 text-[15px] font-semibold text-white">{item.label}</h3>
              <p className="mt-1 text-[13px] leading-snug text-zinc-400">{item.hint}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Shift reminders */}
      <section aria-labelledby="soc-shift-heading">
        <h2 id="soc-shift-heading" className="mb-4 text-lg font-semibold text-white">
          Rappels shift
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {shiftFocus.map((item) => (
            <div
              key={item.title}
              className="flex gap-4 rounded-xl border border-white/[0.07] bg-zinc-900/35 px-5 py-4 ring-1 ring-inset ring-white/[0.03]"
            >
              <div className="mt-0.5 shrink-0">{item.icon}</div>
              <div>
                <h3 className="text-[14px] font-semibold text-zinc-100">{item.title}</h3>
                <p className="mt-1 text-[13px] leading-relaxed text-zinc-500">{item.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
