import type { AlertCatalogItem } from "@/types/alertsCatalog";

/** Normalise la sévérité pour l’agrégation (anglais minuscule). */
export function normSeverity(s: string | undefined): string {
  const x = (s || "autre").toLowerCase().trim();
  if (["critical", "high", "medium", "low", "info"].includes(x)) return x;
  return "autre";
}

export function dayKeyFromIso(iso: string | undefined): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString().slice(0, 10);
  } catch {
    return null;
  }
}

/** Compteurs pour les 4 niveaux affichés sur l’accueil : faible regroupe low, info et autres. */
export type SeverityFourCounts = {
  critical: number;
  high: number;
  medium: number;
  faible: number;
};

export function countAlertsBySeverityFour(alerts: AlertCatalogItem[]): SeverityFourCounts {
  let critical = 0;
  let high = 0;
  let medium = 0;
  let faible = 0;
  for (const a of alerts) {
    const s = normSeverity(a.severity);
    if (s === "critical") critical++;
    else if (s === "high") high++;
    else if (s === "medium") medium++;
    else faible++;
  }
  return { critical, high, medium, faible };
}

export type DayCountRow = { day: string; full: string; count: number };

/** Date ISO pour la courbe : préfère ``attack_start_time``, puis ``attack_end_time``. */
function timelineIsoForAlert(a: AlertCatalogItem): string | undefined {
  const d = a.detection;
  const start = d?.attack_start_time?.trim();
  if (start) return start;
  const end = d?.attack_end_time?.trim();
  if (end) return end;
  return undefined;
}

/** Chronologie journalière UTC à partir des timestamps de détection (start puis end). */
export function alertsTimelineByDayUtc(alerts: AlertCatalogItem[]): DayCountRow[] {
  const byDay: Record<string, number> = {};
  for (const a of alerts) {
    const dk = dayKeyFromIso(timelineIsoForAlert(a));
    if (dk) byDay[dk] = (byDay[dk] || 0) + 1;
  }
  return Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([full, count]) => ({
      full,
      day: full.slice(5),
      count,
    }));
}
