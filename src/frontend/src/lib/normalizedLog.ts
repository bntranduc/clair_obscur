/**
 * Aligné sur ``NormalizedEvent`` / ``RawRef`` (``backend/log/normalization/types.py``).
 */
export type RawRef = {
  raw_id?: string;
  s3_key?: string;
  line?: number;
};

export type NormalizedEvent = {
  /** Présent quand la source est DynamoDB (ingestion ``put_logs_from_s3_to_dynamo_db``). */
  id?: string | null;
  raw_ref?: RawRef;
  timestamp?: string | null;
  log_source?: string | null;
  auth_method?: string | null;
  status?: string | null;
  session_id?: string | null;
  failure_reason?: string | null;
  username?: string | null;
  geolocation_lat?: number | null;
  geolocation_lon?: number | null;
  geolocation_country?: string | null;
  http_method?: string | null;
  uri?: string | null;
  status_code?: number | null;
  response_size?: number | null;
  response_time_ms?: number | null;
  user_agent?: string | null;
  referer?: string | null;
  source_ip?: string | null;
  source_port?: number | null;
  destination_ip?: string | null;
  destination_port?: number | null;
  protocol?: string | null;
  action?: string | null;
  bytes_sent?: number | null;
  bytes_received?: number | null;
  packets?: number | null;
  duration_ms?: number | null;
  hostname?: string | null;
  process?: string | null;
  pid?: number | null;
  facility?: string | null;
  severity?: string | null;
  message?: string | null;
};

/** Colonnes du tableau (ordre = types.py ``NormalizedEvent``). */
export const NORMALIZED_TABLE_COLUMNS: { label: string; path: string[] }[] = [
  { label: "id", path: ["id"] },
  { label: "raw_id", path: ["raw_ref", "raw_id"] },
  { label: "s3_key", path: ["raw_ref", "s3_key"] },
  { label: "line", path: ["raw_ref", "line"] },
  { label: "timestamp", path: ["timestamp"] },
  { label: "log_source", path: ["log_source"] },
  { label: "auth_method", path: ["auth_method"] },
  { label: "status", path: ["status"] },
  { label: "session_id", path: ["session_id"] },
  { label: "failure_reason", path: ["failure_reason"] },
  { label: "username", path: ["username"] },
  { label: "geolocation_lat", path: ["geolocation_lat"] },
  { label: "geolocation_lon", path: ["geolocation_lon"] },
  { label: "geolocation_country", path: ["geolocation_country"] },
  { label: "http_method", path: ["http_method"] },
  { label: "uri", path: ["uri"] },
  { label: "status_code", path: ["status_code"] },
  { label: "response_size", path: ["response_size"] },
  { label: "response_time_ms", path: ["response_time_ms"] },
  { label: "user_agent", path: ["user_agent"] },
  { label: "referer", path: ["referer"] },
  { label: "source_ip", path: ["source_ip"] },
  { label: "source_port", path: ["source_port"] },
  { label: "destination_ip", path: ["destination_ip"] },
  { label: "destination_port", path: ["destination_port"] },
  { label: "protocol", path: ["protocol"] },
  { label: "action", path: ["action"] },
  { label: "bytes_sent", path: ["bytes_sent"] },
  { label: "bytes_received", path: ["bytes_received"] },
  { label: "packets", path: ["packets"] },
  { label: "duration_ms", path: ["duration_ms"] },
  { label: "hostname", path: ["hostname"] },
  { label: "process", path: ["process"] },
  { label: "pid", path: ["pid"] },
  { label: "facility", path: ["facility"] },
  { label: "severity", path: ["severity"] },
  { label: "message", path: ["message"] },
];

export function getByPath(obj: unknown, path: string[]): unknown {
  let cur: unknown = obj;
  for (const key of path) {
    if (cur === null || cur === undefined) return undefined;
    if (typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

export function formatCell(value: unknown, maxLen = 120): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  const s = String(value);
  if (s.length <= maxLen) return s;
  return `${s.slice(0, maxLen)}…`;
}
