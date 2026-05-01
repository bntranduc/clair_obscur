/* eslint-disable @typescript-eslint/no-explicit-any */

/** Appel direct à uvicorn (SSR / scripts) ; le navigateur utilise le proxy par défaut (voir ``next.config``). */
const DEFAULT_API_DIRECT = "http://127.0.0.1:8010";

/** Préfixe servi par Next (rewrite → dashboard) : même origine que la page → évite « Failed to fetch » si tu ouvres le site via ``localhost`` ou une IP LAN au lieu de ``127.0.0.1``. */
const BFF_PREFIX = "/bff-dashboard";

function apiBase(): string {
  const fromEnv = process.env.NEXT_PUBLIC_DASHBOARD_API_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  if (typeof window !== "undefined") return BFF_PREFIX;
  return DEFAULT_API_DIRECT;
}

export type S3ObjectInfo = {
  key: string;
  size: number;
  last_modified: string | null;
};

export type ListS3ObjectsResponse = {
  bucket: string;
  prefix: string;
  objects: S3ObjectInfo[];
  continuation_token?: string | null;
};

/** Aligné sur ``backend.log.normalization.normalize.ALL_FIELDS`` + ``raw_ref`` (fallback si l’API ne renvoie pas ``field_order``). */
export const NORMALIZED_LOG_FIELDS_FALLBACK: readonly string[] = [
  "timestamp",
  "log_source",
  "action",
  "auth_method",
  "bytes_received",
  "bytes_sent",
  "destination_ip",
  "destination_port",
  "duration_ms",
  "facility",
  "failure_reason",
  "geolocation_country",
  "geolocation_lat",
  "geolocation_lon",
  "hostname",
  "http_method",
  "message",
  "packets",
  "pid",
  "process",
  "protocol",
  "referer",
  "response_size",
  "response_time_ms",
  "session_id",
  "severity",
  "source_ip",
  "source_port",
  "status",
  "status_code",
  "uri",
  "user_agent",
  "username",
  "raw_ref",
];

export type S3SampleResponse = {
  bucket: string;
  key: string;
  logs: Record<string, any>[];
  /** Ordre des colonnes = événement normalisé (ALL_FIELDS + raw_ref). */
  field_order?: string[];
  truncated: boolean;
  offset_lines: number;
  limit_lines: number;
};

export async function fetchS3LogObjects(maxKeys = 100): Promise<ListS3ObjectsResponse> {
  const url = `${apiBase()}/api/v1/logs/s3-objects?max_keys=${maxKeys}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`list objects failed ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function fetchS3LogSample(
  key: string,
  opts?: { offsetLines?: number; limitLines?: number }
): Promise<S3SampleResponse> {
  const sp = new URLSearchParams();
  sp.set("key", key);
  if (opts?.offsetLines != null) sp.set("offset_lines", String(opts.offsetLines));
  if (opts?.limitLines != null) sp.set("limit_lines", String(opts.limitLines));
  const url = `${apiBase()}/api/v1/logs/s3-sample?${sp}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`sample failed ${res.status}: ${await res.text()}`);
  return res.json();
}

export type AlertsPool = "prod" | "tmp";

export type ListPredictionsResponse = {
  pool: string;
  bucket: string;
  prefix: string;
  objects: S3ObjectInfo[];
  continuation_token?: string | null;
};

export type PredictionFileResponse = {
  pool: string;
  bucket: string;
  key: string;
  alerts: Record<string, any>[];
  meta: Record<string, any> | null;
};

export async function fetchPredictionObjects(
  pool: AlertsPool,
  maxKeys = 200
): Promise<ListPredictionsResponse> {
  const sp = new URLSearchParams();
  sp.set("pool", pool);
  sp.set("max_keys", String(maxKeys));
  const url = `${apiBase()}/api/v1/alerts/s3-objects?${sp}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`list predictions failed ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function fetchPredictionFile(pool: AlertsPool, key: string): Promise<PredictionFileResponse> {
  const sp = new URLSearchParams();
  sp.set("pool", pool);
  sp.set("key", key);
  const url = `${apiBase()}/api/v1/alerts/prediction?${sp}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`prediction file failed ${res.status}: ${await res.text()}`);
  return res.json();
}
