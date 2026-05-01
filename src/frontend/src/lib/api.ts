/* eslint-disable @typescript-eslint/no-explicit-any */

const DEFAULT_API = "http://127.0.0.1:8010";

/** Si ``1`` : appels navigateur vers ``/api/dashboard-proxy/...`` (serveur → EC2 HTTP, pas de mixed content). */
function useDashboardProxy(): boolean {
  return process.env.NEXT_PUBLIC_DASHBOARD_API_PROXY === "1";
}

/** Base pour les URLs d’API : URL absolue locale/prod, ou préfixe proxy même-origine. */
function apiBase(): string {
  if (useDashboardProxy()) {
    return "/api/dashboard-proxy";
  }
  const raw = process.env.NEXT_PUBLIC_DASHBOARD_API_URL || DEFAULT_API;
  return raw.replace(/\/+$/, "");
}

/** Évite le vague « Failed to fetch » : indique URL + commande backend locale. */
async function dashboardFetch(url: string): Promise<Response> {
  try {
    return await fetch(url, { cache: "no-store" });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (useDashboardProxy()) {
      throw new Error(
        `Proxy dashboard injoignable. Sur Amplify, définis DASHBOARD_API_URL (URL interne http://EC2:8010). ` +
          `Détails : ${msg}`
      );
    }
    throw new Error(
      `API injoignable (${apiBase()}). Lance le backend : depuis la racine du dépôt, ` +
        `\`bash scripts/run_dashboard_api.sh\` (puis \`cd src/frontend && npm run dev\`). ` +
        `Détails : ${msg}`
    );
  }
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
  const res = await dashboardFetch(url);
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
  const res = await dashboardFetch(url);
  if (!res.ok) throw new Error(`sample failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/** Préfixe API : ``/api/v1/alerts`` (prod) ou ``/api/v1/alerts-tmp``. */
export type PredictionsApiPrefix = "/api/v1/alerts" | "/api/v1/alerts-tmp";

export type PredictionsFileResponse = {
  bucket: string;
  key: string;
  meta?: Record<string, unknown> | null;
  alert_count: number;
  rows: Record<string, unknown>[];
  field_order: string[];
};

export async function fetchPredictionS3Objects(
  apiPrefix: PredictionsApiPrefix,
  maxKeys = 200
): Promise<ListS3ObjectsResponse> {
  const url = `${apiBase()}${apiPrefix}/s3-objects?max_keys=${maxKeys}`;
  const res = await dashboardFetch(url);
  if (!res.ok) throw new Error(`list predictions objects failed ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function fetchPredictionsFile(
  apiPrefix: PredictionsApiPrefix,
  key: string
): Promise<PredictionsFileResponse> {
  const sp = new URLSearchParams();
  sp.set("key", key);
  const url = `${apiBase()}${apiPrefix}/s3-predictions?${sp}`;
  const res = await dashboardFetch(url);
  if (!res.ok) throw new Error(`predictions file failed ${res.status}: ${await res.text()}`);
  return res.json();
}
