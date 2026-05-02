import { pathIsConfidenceBranch } from "@/lib/modelFieldLabels";

const ISO_LIKE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

export function formatMaybeIsoDate(value: string): { primary: string; secondary?: string } {
  if (!ISO_LIKE.test(value)) {
    return { primary: value };
  }
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return { primary: value };
    const primary = new Intl.DateTimeFormat("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZoneName: "short",
    }).format(d);
    const secondary = value;
    return { primary, secondary };
  } catch {
    return { primary: value };
  }
}

/** Date/heure de début compacte pour étiquettes (liste alertes). */
export function formatShortDateTime(iso: string): string {
  if (!ISO_LIKE.test(iso)) return iso;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return new Intl.DateTimeFormat("fr-FR", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return iso;
  }
}

/** Probabilités modèle entre 0 et 1 affichées en pourcentage. */
export function formatConfidenceNumber(path: string, n: number): string {
  if (!Number.isFinite(n)) return String(n);
  if (pathIsConfidenceBranch(path) && n >= 0 && n <= 1) {
    return `${Math.round(n * 1000) / 10} %`;
  }
  return String(n);
}
