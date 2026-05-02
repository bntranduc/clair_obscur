"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useState } from "react";
import { PanelTop, X } from "lucide-react";
import type { ModelAlert } from "@/types/modelPrediction";
import { attackDisplayName } from "@/lib/attackLabels";
import { buildUnifiedAlertRows } from "@/lib/buildUnifiedAlertRows";
import { SEVERITY_VISUAL } from "@/lib/severityVisual";
import UnifiedAlertSheet from "@/components/dashboard/UnifiedAlertSheet";
import AlertHeaderBand from "@/components/dashboard/alert-article/AlertHeaderBand";
import AlertTimelineRow from "@/components/dashboard/alert-article/AlertTimelineRow";

export default function AlertPreviewTrigger({ alert }: { alert: ModelAlert }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const sv = SEVERITY_VISUAL[alert.severity];
  const title = attackDisplayName(alert.detection?.attack_type ?? alert.challenge_id);
  const rows = buildUnifiedAlertRows(alert);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, close]);

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.1] bg-white/[0.04] text-zinc-400 transition hover:border-cyan-500/35 hover:bg-cyan-500/10 hover:text-cyan-200"
        aria-label="Aperçu rapide de l’alerte"
        title="Aperçu rapide"
      >
        <PanelTop size={16} strokeWidth={2} aria-hidden />
      </button>

      {open ? (
        <div className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto p-4 sm:p-8" role="presentation">
          <button
            type="button"
            className="fixed inset-0 z-0 bg-black/70 backdrop-blur-[2px]"
            aria-label="Fermer l’aperçu"
            onClick={close}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className={`relative z-10 mt-4 w-full max-w-3xl overflow-hidden rounded-2xl border bg-zinc-950/90 shadow-[0_4px_40px_-12px_rgba(0,0,0,0.65)] ring-1 ring-inset ring-white/[0.06] sm:mt-8 ${sv.heroBorder}`}
          >
            <div className="flex items-center justify-between border-b border-white/[0.08] bg-black/25 px-4 py-3">
              <p id={titleId} className="text-[13px] font-medium text-zinc-200">
                Aperçu — {title}
              </p>
              <button
                type="button"
                onClick={close}
                className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-white/[0.06] hover:text-white"
                aria-label="Fermer"
              >
                <X size={18} />
              </button>
            </div>

            <div className="max-h-[min(78vh,720px)] overflow-y-auto">
              <AlertHeaderBand
                challengeId={alert.challenge_id}
                pipelineSeconds={alert.detection_time_seconds}
                title={title}
                summary={alert.alert_summary}
                severityLabel={sv.label}
                heroGradientClass={sv.hero}
                accentTextClass={sv.heroAccent}
                compact
              />
              <AlertTimelineRow startIso={alert.detection.attack_start_time} endIso={alert.detection.attack_end_time} compact />
              <div className="border-b border-white/[0.06] px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Analyse détaillée</p>
                <p className="mt-1.5 line-clamp-6 text-[12px] leading-relaxed text-zinc-400">{alert.exhaustive_analysis}</p>
                {alert.remediation_proposal ? (
                  <div className="mt-3 rounded-lg border border-emerald-500/25 bg-emerald-500/[0.07] px-3 py-2.5">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-400/90">Remédiation</p>
                    <p className="mt-1 line-clamp-4 text-[11px] leading-relaxed text-zinc-300">{alert.remediation_proposal}</p>
                  </div>
                ) : null}
              </div>
              <div className="px-4 py-3">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
                  Détail modèle — détection, confiance, justification
                </p>
                <UnifiedAlertSheet rows={rows} />
              </div>
              <div className="border-t border-white/[0.06] px-4 py-3">
                <Link
                  href={`/dashboard/alertes/${encodeURIComponent(alert.challenge_id)}`}
                  onClick={close}
                  className="text-[13px] font-medium text-cyan-400 hover:text-cyan-300"
                >
                  Ouvrir la fiche complète →
                </Link>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
