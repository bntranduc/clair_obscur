"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { ModelAlert } from "@/types/modelPrediction";
import { attackDisplayName } from "@/lib/attackLabels";
import { formatShortDateTime } from "@/lib/alertDetailFormat";
import SeverityBadge from "@/components/dashboard/SeverityBadge";
import AlertPreviewTrigger from "@/components/dashboard/AlertPreviewTrigger";
import type { AlertsLayoutMode } from "@/components/dashboard/AlertsListToolbar";
import { alertCardSurfaceClass } from "@/lib/alertCardSeverityStyle";

export default function AlertTicketCard({
  alert,
  layout = "grid",
}: {
  alert: ModelAlert;
  layout?: AlertsLayoutMode;
}) {
  const title = attackDisplayName(alert.detection?.attack_type ?? alert.challenge_id);
  const href = `/dashboard/alertes/${encodeURIComponent(alert.challenge_id)}`;
  const startLabel = formatShortDateTime(alert.detection.attack_start_time);
  const surface = alertCardSurfaceClass(alert.severity);

  if (layout === "row") {
    return (
      <div
        className={`group/card flex flex-col gap-2 rounded-xl px-3 py-2.5 sm:flex-row sm:items-center sm:gap-3 sm:py-2 ${surface}`}
      >
        <div className="flex shrink-0 items-baseline gap-1.5 font-mono text-[11px] tabular-nums text-zinc-500 sm:w-[11rem]">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-zinc-600">Début</span>
          <time dateTime={alert.detection.attack_start_time} className="text-zinc-400">
            {startLabel}
          </time>
        </div>
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 sm:gap-3">
          <Link
            href={href}
            className="min-w-0 shrink font-semibold tracking-tight text-white transition hover:text-blue-100 sm:max-w-[12rem] sm:truncate lg:max-w-[16rem]"
          >
            {title}
          </Link>
          <AlertPreviewTrigger alert={alert} />
          <SeverityBadge level={alert.severity} />
          <Link
            href={href}
            className="min-w-0 flex-1 truncate text-[13px] text-zinc-400 transition hover:text-zinc-200 sm:min-w-[8rem]"
          >
            {alert.alert_summary}
          </Link>
        </div>
        <Link
          href={href}
          className="inline-flex shrink-0 items-center gap-0.5 self-start text-[12px] font-medium text-blue-400/90 transition hover:text-blue-300 sm:self-center"
        >
          <span>Ouvrir</span>
          <ChevronRight size={15} className="transition group-hover/card:translate-x-0.5" aria-hidden />
        </Link>
      </div>
    );
  }

  return (
    <div className={`group/card flex flex-col gap-3 rounded-2xl p-5 ${surface}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500">Type d’attaque</p>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              href={href}
              className="min-w-0 shrink text-lg font-semibold tracking-tight text-white transition hover:text-blue-100 sm:truncate"
            >
              {title}
            </Link>
            <span className="hidden text-zinc-700 sm:inline" aria-hidden>
              ·
            </span>
            <span className="flex min-w-0 items-center gap-1.5 text-[11px] text-zinc-500">
              <span className="shrink-0 font-semibold uppercase tracking-wide text-zinc-600">Début</span>
              <time
                dateTime={alert.detection.attack_start_time}
                className="font-mono tabular-nums text-zinc-400"
              >
                {startLabel}
              </time>
            </span>
            <AlertPreviewTrigger alert={alert} />
          </div>
        </div>
        <SeverityBadge level={alert.severity} />
      </div>
      <Link href={href} className="line-clamp-2 text-[13px] leading-relaxed text-zinc-400 transition hover:text-zinc-200">
        {alert.alert_summary}
      </Link>
      <Link
        href={href}
        className="mt-0.5 inline-flex items-center gap-1 text-[12px] font-medium text-blue-400/90 transition hover:text-blue-300"
      >
        <span>Ouvrir le ticket</span>
        <ChevronRight size={16} className="transition group-hover/card:translate-x-0.5" aria-hidden />
      </Link>
    </div>
  );
}
