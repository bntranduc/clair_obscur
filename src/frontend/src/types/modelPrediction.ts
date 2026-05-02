export type SeverityLevel = "low" | "medium" | "high" | "critical";

export interface ModelDetection {
  attack_type: string;
  attacker_ips: string[];
  victim_accounts: string[];
  attack_start_time: string;
  attack_end_time: string;
  indicators: Record<string, unknown>;
}

export interface ModelAlert {
  challenge_id: string;
  severity: SeverityLevel;
  alert_summary: string;
  detection: ModelDetection;
  detection_time_seconds: number;
  confidence: Record<string, unknown>;
  reasons: Record<string, unknown>;
  exhaustive_analysis: string;
  /** Actions de remédiation proposées (distinct de l’analyse narrative). */
  remediation_proposal?: string;
}

export interface PredictionsPayload {
  alerts: ModelAlert[];
}
