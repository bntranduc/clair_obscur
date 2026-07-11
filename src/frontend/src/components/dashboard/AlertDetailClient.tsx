"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import UnifiedAlertSheet from "@/components/dashboard/UnifiedAlertSheet";
import AlertHeaderBand from "@/components/dashboard/alert-article/AlertHeaderBand";
import AlertTimelineRow from "@/components/dashboard/alert-article/AlertTimelineRow";
import { buildUnifiedAlertRows } from "@/lib/buildUnifiedAlertRows";
import { fetchAllAlerts } from "@/lib/api";
import { attackDisplayName } from "@/lib/attackLabels";
import { SEVERITY_VISUAL } from "@/lib/severityVisual";
import type { AlertCatalogItem, SeverityLevel } from "@/types/alertsCatalog";

const BODY_PAD = "px-5 sm:px-10 lg:px-16 xl:px-24 2xl:px-28";

function isSeverityLevel(v: string): v is SeverityLevel {
  return v === "low" || v === "medium" || v === "high" || v === "critical";
}

export default function AlertDetailClient() {
  const params = useParams<{ challengeId: string }>();
  const challengeId = decodeURIComponent(params.challengeId ?? "");
  const [alert, setAlert] = useState<AlertCatalogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchAllAlerts();
        const found = data.alerts.find((a) => a.challenge_id === challengeId) ?? null;
        if (!cancelled) setAlert(found);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [challengeId]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-3 text-zinc-400">
        <Loader2 className="animate-spin" size={22} aria-hidden />
        Chargement de l’alerte…
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${BODY_PAD} py-8`}>
        <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-6 py-8 text-sm text-red-200">
          {error}
        </p>
      </div>
    );
  }

  if (!alert?.detection) {
    return (
      <div className={`${BODY_PAD} py-8`}>
        <Link
          href="/dashboard/alertes"
          className="group inline-flex items-center gap-2 text-[12px] font-medium text-zinc-500 transition hover:text-blue-300"
        >
          <ArrowLeft size={14} className="transition group-hover:-translate-x-0.5" aria-hidden />
          Retour aux alertes
        </Link>
        <p className="mt-6 text-zinc-400">Alerte introuvable.</p>
      </div>
    );
  }

  const severity = isSeverityLevel(alert.severity) ? alert.severity : "medium";
  const title = attackDisplayName(alert.detection.attack_type ?? alert.challenge_id);
  const sv = SEVERITY_VISUAL[severity];
  const rows = buildUnifiedAlertRows(alert);

  return (
    <article className="w-full pb-16">
      <div className={`mb-6 ${BODY_PAD}`}>
        <Link
          href="/dashboard/alertes"
          className="group inline-flex items-center gap-2 text-[12px] font-medium text-zinc-500 transition hover:text-blue-300"
        >
          <ArrowLeft size={14} className="transition group-hover:-translate-x-0.5" aria-hidden />
          Retour aux alertes
        </Link>
      </div>

      <div className={BODY_PAD}>
        <div
          className={`overflow-hidden rounded-2xl border bg-zinc-950/85 shadow-[0_4px_40px_-12px_rgba(0,0,0,0.65)] ring-1 ring-inset ring-white/[0.06] ${sv.heroBorder}`}
        >
          <AlertHeaderBand
            challengeId={alert.challenge_id}
            pipelineSeconds={alert.detection_time_seconds}
            title={title}
            summary={alert.alert_summary}
            severityLabel={sv.label}
            heroGradientClass={sv.hero}
            accentTextClass={sv.heroAccent}
          />

          <AlertTimelineRow
            startIso={alert.detection.attack_start_time ?? ""}
            endIso={alert.detection.attack_end_time ?? ""}
          />

          <div className="px-5 py-10 sm:px-8 sm:py-12 lg:px-12 xl:px-14 2xl:px-16">
            <div className="grid grid-cols-1 gap-12 xl:grid-cols-12 xl:gap-x-12 2xl:gap-x-16">
              <section className="xl:col-span-5">
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Analyse détaillée</h2>
                <p className="mt-4 text-[15px] leading-[1.8] text-zinc-300 sm:text-[16px]">
                  {alert.exhaustive_analysis ?? "—"}
                </p>
                {alert.remediation_proposal ? (
                  <div className="mt-10 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] px-4 py-4 sm:px-5">
                    <h3 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-400/90">
                      Remédiation proposée
                    </h3>
                    <p className="mt-3 whitespace-pre-wrap text-[14px] leading-[1.75] text-zinc-200 sm:text-[15px]">
                      {alert.remediation_proposal}
                    </p>
                  </div>
                ) : null}
              </section>
              <section className="min-w-0 border-t border-white/[0.06] pt-10 xl:col-span-7 xl:border-l xl:border-t-0 xl:pl-10 xl:pt-0 2xl:pl-14">
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                  Détail modèle — détection, confiance, justification
                </h2>
                <div className="mt-5">
                  <UnifiedAlertSheet rows={rows} />
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
