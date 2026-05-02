import type { SeverityLevel } from "@/types/modelPrediction";

/** Fond et bordure d’étiquette alerte selon la criticité (bordure lisible, fond teinté). */
export function alertCardSurfaceClass(severity: SeverityLevel): string {
  const inset = "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] transition-all border-2";
  switch (severity) {
    case "low":
      return `${inset} border-emerald-500/40 bg-gradient-to-br from-emerald-950/50 via-zinc-900/28 to-zinc-950/50 hover:border-emerald-400/55 hover:from-emerald-950/60`;
    case "medium":
      return `${inset} border-amber-500/40 bg-gradient-to-br from-amber-950/45 via-zinc-900/30 to-zinc-950/50 hover:border-amber-400/55 hover:from-amber-950/55`;
    case "high":
      return `${inset} border-orange-500/45 bg-gradient-to-br from-orange-950/52 via-zinc-900/32 to-zinc-950/52 hover:border-orange-400/60 hover:from-orange-950/62`;
    case "critical":
      return `${inset} border-red-500/50 bg-gradient-to-br from-red-950/55 via-zinc-900/35 to-zinc-950/55 hover:border-red-400/65 hover:from-red-950/70`;
  }
}
