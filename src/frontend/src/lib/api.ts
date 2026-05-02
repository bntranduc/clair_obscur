/* eslint-disable @typescript-eslint/no-explicit-any */

const DEFAULT_SERVER_DIRECT = "http://127.0.0.1:8020";

/** Même origine en navigateur (rewrite Next → API). */
const BFF_PREFIX = "/bff-api";

function apiBase(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  if (typeof window !== "undefined") return BFF_PREFIX;
  return DEFAULT_SERVER_DIRECT;
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

export {
  NORMALIZED_TABLE_COLUMNS,
  NORMALIZED_TABLE_COLUMNS as NORMALIZED_EVENT_COLUMNS,
  NORMALIZED_TABLE_COLUMNS as NORMALIZED_LOG_FIELDS_FALLBACK,
} from "./normalizedTable";

export type S3SampleResponse = {
  bucket: string;
  key: string;
  logs: Record<string, any>[];
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

export type ChatRole = "user" | "assistant";

export type ChatMessage = { role: ChatRole; content: string };

export async function postChat(messages: ChatMessage[]): Promise<{ reply: string }> {
  const url = `${apiBase()}/api/v1/chat`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      const j = JSON.parse(detail) as { detail?: unknown };
      if (j.detail !== undefined) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* raw text */
    }
    throw new Error(`chat ${res.status}: ${detail.slice(0, 800)}`);
  }
  return res.json() as Promise<{ reply: string }>;
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
