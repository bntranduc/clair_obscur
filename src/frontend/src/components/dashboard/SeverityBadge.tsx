import type { SeverityLevel } from "@/types/alertsCatalog";

const STYLES: Record<SeverityLevel, string> = {
  low: "bg-emerald-500/15 text-emerald-200 ring-emerald-400/25",
  medium: "bg-amber-500/15 text-amber-100 ring-amber-400/25",
  high: "bg-orange-500/15 text-orange-100 ring-orange-400/30",
  critical: "bg-red-600/20 text-red-100 ring-red-500/35",
};

const LABELS: Record<SeverityLevel, string> = {
  low: "Faible",
  medium: "Moyen",
  high: "Élevé",
  critical: "Critique",
};

export default function SeverityBadge({ level }: { level: SeverityLevel | string }) {
  const key =
    level === "low" || level === "medium" || level === "high" || level === "critical" ? level : "medium";
  return (
    <span
      className={`inline-flex items-center rounded-lg px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${STYLES[key]}`}
    >
      {LABELS[key]}
    </span>
  );
}
