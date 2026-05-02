/**
 * Colonnes alignées sur ``NormalizedEvent`` + ``RawRef``
 * (``src/backend/log/normalization/types.py``).
 * ``raw_ref`` n’est pas une colonne : on affiche ``raw_id``, ``s3_key``, ``line``.
 */
export const NORMALIZED_TABLE_COLUMNS = [
  "raw_id",
  "s3_key",
  "line",
  "timestamp",
  "log_source",
  "auth_method",
  "status",
  "session_id",
  "failure_reason",
  "username",
  "geolocation_lat",
  "geolocation_lon",
  "geolocation_country",
  "http_method",
  "uri",
  "status_code",
  "response_size",
  "response_time_ms",
  "user_agent",
  "referer",
  "source_ip",
  "source_port",
  "destination_ip",
  "destination_port",
  "protocol",
  "action",
  "bytes_sent",
  "bytes_received",
  "packets",
  "duration_ms",
  "hostname",
  "process",
  "pid",
  "facility",
  "severity",
  "message",
] as const;

export type NormalizedTableColumn = (typeof NORMALIZED_TABLE_COLUMNS)[number];

const RAW_REF_COLUMNS = new Set<string>(["raw_id", "s3_key", "line"]);

/** Lit une valeur scalaire dans une ligne normalisée (y compris sous-champs de ``raw_ref``). */
export function getNormalizedCell(row: Record<string, unknown>, col: NormalizedTableColumn): unknown {
  if (RAW_REF_COLUMNS.has(col)) {
    const ref = row.raw_ref;
    if (ref && typeof ref === "object" && !Array.isArray(ref)) {
      return (ref as Record<string, unknown>)[col];
    }
    return undefined;
  }
  return row[col];
}

/** Affichage tableau : pas de JSON ; uniquement chaînes / nombres / booléens. */
export function formatScalarCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v === "" ? "—" : v;
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "bigint") return String(v);
  return "—";
}
