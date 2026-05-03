import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import UnifiedAlertSheet from "@/components/dashboard/UnifiedAlertSheet";
import AlertHeaderBand from "@/components/dashboard/alert-article/AlertHeaderBand";
import AlertTimelineRow from "@/components/dashboard/alert-article/AlertTimelineRow";
import { buildUnifiedAlertRows } from "@/lib/buildUnifiedAlertRows";
import { getFakeAlertByChallengeId } from "@/lib/fakePredictions";
import { attackDisplayName } from "@/lib/attackLabels";
import { SEVERITY_VISUAL } from "@/lib/severityVisual";

type Props = { params: Promise<{ challengeId: string }> };

const BODY_PAD = "px-5 sm:px-10 lg:px-16 xl:px-24 2xl:px-28";

export async function generateMetadata({ params }: Props) {
  const { challengeId } = await params;
  const alert = getFakeAlertByChallengeId(decodeURIComponent(challengeId));
  if (!alert) return { title: "Alerte introuvable" };
  const name = attackDisplayName(alert.detection?.attack_type ?? alert.challenge_id);
  return { title: `${name} — Alertes` };
}

export default async function AlertDetailPage({ params }: Props) {
  const { challengeId: raw } = await params;
  const challengeId = decodeURIComponent(raw);
  const alert = getFakeAlertByChallengeId(challengeId);
  if (!alert) notFound();

  const title = attackDisplayName(alert.detection?.attack_type ?? alert.challenge_id);
  const sv = SEVERITY_VISUAL[alert.severity];
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

          <AlertTimelineRow startIso={alert.detection.attack_start_time} endIso={alert.detection.attack_end_time} />

          <div className="px-5 py-10 sm:px-8 sm:py-12 lg:px-12 xl:px-14 2xl:px-16">
            <div className="grid grid-cols-1 gap-12 xl:grid-cols-12 xl:gap-x-12 2xl:gap-x-16">
              <section className="xl:col-span-5">
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Analyse détaillée</h2>
                <p className="mt-4 text-[15px] leading-[1.8] text-zinc-300 sm:text-[16px]">{alert.exhaustive_analysis}</p>
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

          <p className="border-t border-white/[0.06] px-5 py-4 text-center text-[10px] text-zinc-600 sm:px-8">
            Jeu de démonstration — format aligné sur l’API modèle
          </p>
        </div>
      </div>
    </article>
  );
}
