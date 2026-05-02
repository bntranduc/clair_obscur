import type { SeverityLevel } from "@/types/modelPrediction";

/** Accent couleur par niveau de criticité (fiche alerte compacte). */
export const SEVERITY_VISUAL: Record<
  SeverityLevel,
  { label: string; hero: string; heroBorder: string; heroAccent: string }
> = {
  low: {
    label: "Faible",
    hero: "from-emerald-950/90 via-zinc-950/80 to-zinc-950",
    heroBorder: "border-emerald-500/35",
    heroAccent: "text-emerald-300",
  },
  medium: {
    label: "Moyen",
    hero: "from-amber-950/90 via-zinc-950/80 to-zinc-950",
    heroBorder: "border-amber-500/40",
    heroAccent: "text-amber-200",
  },
  high: {
    label: "Élevé",
    hero: "from-orange-950/95 via-zinc-950/85 to-zinc-950",
    heroBorder: "border-orange-500/45",
    heroAccent: "text-orange-200",
  },
  critical: {
    label: "Critique",
    hero: "from-red-950/95 via-zinc-950/90 to-zinc-950",
    heroBorder: "border-red-500/50",
    heroAccent: "text-red-200",
  },
};
