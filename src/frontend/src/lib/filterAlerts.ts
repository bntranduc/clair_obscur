import type { ModelAlert, SeverityLevel } from "@/types/modelPrediction";

export type AlertsFilterState = {
  /** Valeur de `detection.attack_type` ; chaîne vide = tous */
  attackType: string;
  /** Vide = toutes les criticités */
  severity: "" | SeverityLevel;
  /** `YYYY-MM-DD` ; vide = pas de borne */
  dateFrom: string;
  dateTo: string;
};

export const defaultAlertsFilterState = (): AlertsFilterState => ({
  attackType: "",
  severity: "",
  dateFrom: "",
  dateTo: "",
});

function startOfDayLocal(ymd: string): number | null {
  if (!ymd.trim()) return null;
  const p = ymd.split("-").map(Number);
  if (p.length !== 3 || p.some((n) => Number.isNaN(n))) return null;
  const [y, m, d] = p;
  return new Date(y, m - 1, d, 0, 0, 0, 0).getTime();
}

function endOfDayLocal(ymd: string): number | null {
  if (!ymd.trim()) return null;
  const p = ymd.split("-").map(Number);
  if (p.length !== 3 || p.some((n) => Number.isNaN(n))) return null;
  const [y, m, d] = p;
  return new Date(y, m - 1, d, 23, 59, 59, 999).getTime();
}

/** Fenêtre d’attaque [start, end] doit intersecter [dateFrom 00:00, dateTo 23:59] local (bornes optionnelles). */
export function filterAlerts(alerts: ModelAlert[], f: AlertsFilterState): ModelAlert[] {
  const fromMs = f.dateFrom ? startOfDayLocal(f.dateFrom) : null;
  const toMs = f.dateTo ? endOfDayLocal(f.dateTo) : null;

  return alerts.filter((a) => {
    if (f.attackType && a.detection.attack_type !== f.attackType) return false;
    if (f.severity && a.severity !== f.severity) return false;

    const as = new Date(a.detection.attack_start_time).getTime();
    const ae = new Date(a.detection.attack_end_time).getTime();

    if (fromMs != null && ae < fromMs) return false;
    if (toMs != null && as > toMs) return false;
    return true;
  });
}

export function uniqueAttackTypes(alerts: ModelAlert[]): string[] {
  return [...new Set(alerts.map((a) => a.detection.attack_type))].sort((x, y) =>
    x.localeCompare(y, "fr"),
  );
}
