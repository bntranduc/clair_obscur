/* eslint-disable @typescript-eslint/no-explicit-any */

/** Si ``1`` : appels navigateur vers ``/api/dashboard-proxy/...`` (serveur → EC2 HTTP, pas de mixed content). */
function useDashboardProxy(): boolean {
  return process.env.NEXT_PUBLIC_DASHBOARD_API_PROXY === "1";
}

/**
 * Base pour les URLs d’API : pas de fallback localhost — uniquement variables d’environnement
 * (URL publique EC2 ou proxy Amplify).
 */
function apiBase(): string {
  if (useDashboardProxy()) {
    return "/api/dashboard-proxy";
  }
  const raw = process.env.NEXT_PUBLIC_DASHBOARD_API_URL?.trim();
  if (!raw) {
    throw new Error(
      "NEXT_PUBLIC_DASHBOARD_API_URL est obligatoire (URL publique du dashboard API, ex. http://ec2-….amazonaws.com:8010). " +
        "Sur Amplify en HTTPS : NEXT_PUBLIC_DASHBOARD_API_PROXY=1 et DASHBOARD_API_URL côté serveur. Voir src/frontend/.env.example."
    );
  }
  return raw.replace(/\/+$/, "");
}

/** Navigateur HTTPS → API HTTP : blocage mixed-content avant tout réseau (« Failed to fetch »). */
function throwIfMixedContentWouldBlock(url: string): void {
  if (typeof window === "undefined") return;
  if (window.location.protocol !== "https:") return;
  if (useDashboardProxy()) return;
  const base = apiBase();
  if (base.startsWith("http://") || url.startsWith("http://")) {
    throw new Error(
      "Mixed content : la page est en HTTPS mais l’API dashboard est en HTTP ; le navigateur bloque l’appel (Failed to fetch). " +
        "Solution : définir NEXT_PUBLIC_DASHBOARD_API_PROXY=1 et DASHBOARD_API_URL (URL EC2:8010) côté serveur Next.js / Amplify. " +
        "Voir src/frontend/.env.example."
    );
  }
}

/** Évite le vague « Failed to fetch » avec un message exploitable. */
async function dashboardFetch(url: string): Promise<Response> {
  throwIfMixedContentWouldBlock(url);
  try {
    return await fetch(url, { cache: "no-store" });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (useDashboardProxy()) {
      throw new Error(
        `Proxy dashboard injoignable. Définis DASHBOARD_API_URL (http://EC2:8010) côté serveur Amplify / runtime. ` +
          `Détails : ${msg}`
      );
    }
    const hint =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? " Si tu es sur un site HTTPS (ex. Amplify), utilise le proxy (NEXT_PUBLIC_DASHBOARD_API_PROXY=1)."
        : "";
    throw new Error(
      `API injoignable (${apiBase()}). Vérifie EC2, security group :8010, CORS.${hint} Détails : ${msg}`
    );
  }
}

async function dashboardFetchPost(url: string, jsonBody: unknown): Promise<Response> {
  throwIfMixedContentWouldBlock(url);
  try {
    return await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(jsonBody),
      cache: "no-store",
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (useDashboardProxy()) {
      throw new Error(
        `Proxy dashboard injoignable. Définis DASHBOARD_API_URL (http://EC2:8010) côté serveur Amplify / runtime. ` +
          `Détails : ${msg}`
      );
    }
    const hint =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? " Si tu es sur un site HTTPS (ex. Amplify), utilise NEXT_PUBLIC_DASHBOARD_API_PROXY=1."
        : "";
    throw new Error(
      `API injoignable (${apiBase()}). Vérifie EC2, security group :8010, CORS.${hint} Détails : ${msg}`
    );
  }
}

/** Appelle ``POST /api/v1/model/predict`` (proxy dashboard → service modèle). */
export async function callModelPredict(
  events: Record<string, unknown>[]
): Promise<Record<string, unknown>> {
  const url = `${apiBase()}/api/v1/model/predict`;
  const res = await dashboardFetchPost(url, { events });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`predict failed ${res.status}: ${text}`);
  }
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    throw new Error(`predict: réponse non-JSON: ${text.slice(0, 500)}`);
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
