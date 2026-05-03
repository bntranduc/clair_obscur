import type { ModelAlert, SeverityLevel } from "@/types/modelPrediction";
import { formatMaybeIsoDate } from "@/lib/alertDetailFormat";
import { fieldLabelFr } from "@/lib/modelFieldLabels";

const SEVERITY_FR: Record<SeverityLevel, string> = {
  low: "Faible",
  medium: "Moyen",
  high: "Élevé",
  critical: "Critique",
};

export type UnifiedRow = {
  id: string;
  /** Libellé affiché (une seule fois pour les lignes groupées IP / comptes). */
  label: string;
  /** Sous-ligne sans répéter le titre de section */
  isContinuation?: boolean;
  value: string;
  score?: number;
  reason?: string;
};

function asNum(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

function asStr(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}

function formatPrimitive(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "oui" : "non";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function formatIndicatorsObject(ind: Record<string, unknown>): string {
  return Object.entries(ind)
    .map(([k, v]) => `${fieldLabelFr(k)} : ${formatPrimitive(v)}`)
    .join(" · ");
}

/** Aplatit alerte en lignes fusionnées détection + confiance + justification. */
export function buildUnifiedAlertRows(alert: ModelAlert): UnifiedRow[] {
  const conf = alert.confidence as Record<string, unknown>;
  const reasons = alert.reasons as Record<string, unknown>;
  const confDet = (conf.detection as Record<string, unknown>) ?? {};
  const reasDet = (reasons.detection as Record<string, unknown>) ?? {};
  const det = alert.detection;

  const rows: UnifiedRow[] = [];

  rows.push({
    id: "challenge_id",
    label: fieldLabelFr("challenge_id"),
    value: alert.challenge_id,
    score: asNum(conf.challenge_id),
    reason: asStr(reasons.challenge_id),
  });

  rows.push({
    id: "severity",
    label: fieldLabelFr("severity"),
    value: SEVERITY_FR[alert.severity] ?? alert.severity,
    score: asNum(conf.severity),
    reason: asStr(reasons.severity),
  });

  rows.push({
    id: "alert_summary",
    label: fieldLabelFr("alert_summary"),
    value: alert.alert_summary,
    score: asNum(conf.alert_summary),
    reason: asStr(reasons.alert_summary),
  });

  rows.push({
    id: "remediation_proposal",
    label: fieldLabelFr("remediation_proposal"),
    value: alert.remediation_proposal?.trim() || "—",
    score: asNum(conf.remediation_proposal),
    reason: asStr(reasons.remediation_proposal),
  });

  rows.push({
    id: "detection_time_seconds",
    label: fieldLabelFr("detection_time_seconds"),
    value: `${alert.detection_time_seconds} s`,
    score: asNum(conf.detection_time_seconds),
    reason: asStr(reasons.detection_time_seconds),
  });

  rows.push({
    id: "attack_type",
    label: fieldLabelFr("attack_type"),
    value: det.attack_type,
    score: asNum(confDet.attack_type),
    reason: asStr(reasDet.attack_type),
  });

  const ips = det.attacker_ips ?? [];
  const ipScores = confDet.attacker_ips;
  const ipReasons = reasDet.attacker_ips;
  const scArr = Array.isArray(ipScores) ? ipScores : [];
  const rsArr = Array.isArray(ipReasons) ? ipReasons : [];

  ips.forEach((ip, i) => {
    rows.push({
      id: `attacker_ip_${i}`,
      label: i === 0 ? fieldLabelFr("attacker_ips") : "",
      isContinuation: i > 0,
      value: ip,
      score: asNum(scArr[i]),
      reason: asStr(rsArr[i]),
    });
  });

  const victims = det.victim_accounts ?? [];
  const vScores = confDet.victim_accounts;
  const vReasons = reasDet.victim_accounts;
  const vsArr = Array.isArray(vScores) ? vScores : [];
  const vrArr = Array.isArray(vReasons) ? vReasons : [];

  victims.forEach((acct, i) => {
    rows.push({
      id: `victim_${i}`,
      label: i === 0 ? fieldLabelFr("victim_accounts") : "",
      isContinuation: i > 0,
      value: acct,
      score: asNum(vsArr[i]),
      reason: asStr(vrArr[i]),
    });
  });

  rows.push({
    id: "attack_start_time",
    label: fieldLabelFr("attack_start_time"),
    value: formatMaybeIsoDate(det.attack_start_time).primary,
    score: asNum(confDet.attack_start_time),
    reason: asStr(reasDet.attack_start_time),
  });

  rows.push({
    id: "attack_end_time",
    label: fieldLabelFr("attack_end_time"),
    value: formatMaybeIsoDate(det.attack_end_time).primary,
    score: asNum(confDet.attack_end_time),
    reason: asStr(reasDet.attack_end_time),
  });

  const ind = det.indicators as Record<string, unknown>;
  if (ind && Object.keys(ind).length > 0) {
    rows.push({
      id: "indicators",
      label: fieldLabelFr("indicators"),
      value: formatIndicatorsObject(ind),
      score: asNum(confDet.indicators),
      reason: asStr(reasDet.indicators),
    });
  }

  return rows;
}

export function scoreToneClass(p: number): string {
  if (p >= 0.88) return "text-emerald-400";
  if (p >= 0.75) return "text-blue-400";
  if (p >= 0.6) return "text-amber-300";
  return "text-orange-400";
}
