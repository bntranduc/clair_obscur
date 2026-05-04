/** Réponse ``GET /api/v1/alerts`` — catalogue JSON (futur : base dédiée). */

export type AlertDetection = {
  attack_type?: string;
  attacker_ips?: string[];
  victim_accounts?: string[];
  attack_start_time?: string;
  attack_end_time?: string;
  indicators?: Record<string, unknown>;
};

export type AlertConfidence = {
  challenge_id?: number;
  severity?: number;
  alert_summary?: number;
  remediation_proposal?: number;
  detection?: unknown;
  detection_time_seconds?: number;
};

export type AlertCatalogItem = {
  id: string;
  numeric_id?: number;
  challenge_id: string;
  severity: string;
  alert_summary: string;
  detection?: AlertDetection;
  detection_time_seconds?: number;
  confidence?: AlertConfidence;
};

export type AlertsCatalogResponse = {
  alerts: AlertCatalogItem[];
  count: number;
  source_path?: string;
};
