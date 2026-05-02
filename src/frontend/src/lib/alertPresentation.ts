/**
 * Normalise les alertes JSON (pipeline modèle, OpenSearch hit, etc.) pour l’UI.
 */

export type AlertCardModel = {
  id: string;
  challengeId: string;
  attackType: string;
  attackerIps: string[];
  victimAccounts: string[];
  windowLabel: string | null;
  detectionTimeSec: number | null;
  indicatorsPreview: string | null;
  raw: Record<string, unknown>;
};

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

function pickWindow(base: Record<string, unknown>, det: Record<string, unknown> | null): string | null {
  const aw = asRecord(base.attack_window);
  if (aw?.start && aw?.end) return `${String(aw.start)} → ${String(aw.end)}`;
  if (det?.attack_start_time && det?.attack_end_time)
    return `${String(det.attack_start_time)} → ${String(det.attack_end_time)}`;
  if (det?.attack_start_time) return String(det.attack_start_time);
  return null;
}

function indicatorsShort(ind: unknown): string | null {
  const o = asRecord(ind);
  if (!o) return null;
  const keys = Object.keys(o);
  if (keys.length === 0) return null;
  const parts = keys.slice(0, 4).map((k) => {
    const v = o[k];
    if (v === null || v === undefined) return `${k}: —`;
    if (typeof v === "object") return `${k}: …`;
    return `${k}: ${String(v)}`;
  });
  return parts.join(" · ");
}

/** Transforme une alerte API en modèle carte (indices visibles + raw pour détails). */
export function alertToCardModel(alert: unknown, index: number): AlertCardModel {
  const fallbackId = `alert-${index}`;
  if (!alert || typeof alert !== "object" || Array.isArray(alert)) {
    return {
      id: fallbackId,
      challengeId: "—",
      attackType: "Type inconnu",
      attackerIps: [],
      victimAccounts: [],
      windowLabel: null,
      detectionTimeSec: null,
      indicatorsPreview: null,
      raw: {},
    };
  }

  const root = alert as Record<string, unknown>;
  const det = asRecord(root.detection);
  const src = asRecord(root._source);
  const base = det ?? src ?? root;

  const challengeId = String(root.challenge_id ?? base.challenge_id ?? base.attack_type ?? `#${index + 1}`);
  const attackType = String(base.attack_type ?? root.challenge_id ?? challengeId);

  const attackerIps = asStringArray(det?.attacker_ips ?? base.attacker_ips);
  const victimAccounts = asStringArray(det?.victim_accounts ?? base.victim_accounts);

  const windowLabel = pickWindow(base, det);
  const detTime = root.detection_time_seconds;
  const detectionTimeSec = typeof detTime === "number" && Number.isFinite(detTime) ? detTime : null;

  const indicatorsPreview = indicatorsShort(det?.indicators ?? base.indicators);

  return {
    id: String(root._id ?? challengeId ?? fallbackId),
    challengeId,
    attackType,
    attackerIps,
    victimAccounts,
    windowLabel,
    detectionTimeSec,
    indicatorsPreview,
    raw: root,
  };
}
