/** Bandeau d’en-tête alerte (réutilisable fiche + aperçu). */
export default function AlertHeaderBand({
  challengeId,
  pipelineSeconds,
  title,
  summary,
  severityLabel,
  heroGradientClass,
  accentTextClass,
  compact,
}: {
  challengeId: string;
  pipelineSeconds: number;
  title: string;
  summary: string;
  severityLabel: string;
  heroGradientClass: string;
  accentTextClass: string;
  compact?: boolean;
}) {
  const innerPad = compact ? "px-4 py-3" : "px-5 py-5 sm:px-10 sm:py-7 lg:px-16 lg:py-8 xl:px-24 2xl:px-28";
  return (
    <div className={`bg-gradient-to-r ${heroGradientClass} border-b border-white/[0.07]`}>
      <div className={innerPad}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-zinc-500">
              <span className="font-mono text-zinc-400">{challengeId}</span>
              <span aria-hidden className="text-zinc-700">
                ·
              </span>
              <span>Pipeline {pipelineSeconds}s</span>
            </div>
            <h1
              className={`mt-1 font-semibold leading-tight text-white ${compact ? "text-base" : "text-xl sm:text-2xl lg:text-3xl"}`}
            >
              {title}
            </h1>
            <p
              className={`mt-1.5 leading-snug text-zinc-400 ${compact ? "line-clamp-3 text-[12px]" : "text-[13px] sm:text-[15px]"}`}
            >
              {summary}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className={`text-[9px] font-bold uppercase tracking-[0.18em] ${accentTextClass}`}>Criticité</p>
            <p className={`font-bold leading-none ${accentTextClass} ${compact ? "text-lg" : "text-2xl sm:text-3xl"}`}>
              {severityLabel}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
