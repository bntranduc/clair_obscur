import type { NormalizedEvent } from "@/lib/normalizedLog";
import type { AlertsCatalogResponse } from "@/types/alertsCatalog";
import type { SiemDashboard } from "@/types/siemAnalytics";
import type { VmActionResponse, VmsListResponse } from "@/types/vms";
import { getBackendBaseUrl } from "@/lib/apiBackendUrl";

/** URL de base FastAPI (ex. EC2). Équivaut à un ``curl`` sur la même URL. */
function getApiUrl(): string {
  return getBackendBaseUrl();
}

/** Même origine CORS que l’API (``allow_credentials=False`` → pas de cookies cross-origin). */
const apiFetchInit: RequestInit = { cache: "no-store", credentials: "omit" };

/** Pagination offset (S3 raw-logs via API — bucket / préfixe lus côté serveur). */
export type NormalizedLogsS3Page = {
  items: NormalizedEvent[];
  has_more: boolean;
  skip: number;
  limit: number;
};

export type FetchNormalizedLogsS3Options = {
  raw_logs_bucket?: string;
  raw_logs_prefix?: string;
  region?: string;
};

/** Pagination par curseur (DynamoDB) — pas de clés AWS dans l’URL. */
export type NormalizedLogsDynamoPage = {
  items: NormalizedEvent[];
  has_more: boolean;
  next_start_key: string | null;
  limit: number;
  pk: string;
};

export type FetchNormalizedLogsDynamoOptions = {
  pk?: string;
  region?: string;
};

/** Partition DynamoDB côté navigateur (build Next) — alias de ``DYNAMODB_PK`` côté API. */
function dynamoPkFromEnv(): string | undefined {
  if (typeof process === "undefined" || !process.env?.NEXT_PUBLIC_DYNAMODB_PK) return undefined;
  const v = process.env.NEXT_PUBLIC_DYNAMODB_PK.trim();
  return v || undefined;
}

/** Logs normalisés depuis le bucket S3 raw-logs (``RAW_LOGS_BUCKET`` / ``RAW_LOGS_PREFIX`` côté API). */
export async function fetchNormalizedLogsFromS3(
  params: { skip?: number; limit?: number },
  options?: FetchNormalizedLogsS3Options,
): Promise<NormalizedLogsS3Page> {
  const sp = new URLSearchParams();
  sp.set("skip", String(params.skip ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  if (options?.raw_logs_bucket?.trim()) sp.set("raw_logs_bucket", options.raw_logs_bucket.trim());
  if (options?.raw_logs_prefix?.trim()) sp.set("raw_logs_prefix", options.raw_logs_prefix.trim());
  if (options?.region?.trim()) sp.set("region", options.region.trim());
  const q = sp.toString();
  const url = `${getApiUrl()}/api/v1/logs/normalized${q ? `?${q}` : ""}`;
  const res = await fetch(url, apiFetchInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = text;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail))
        detail = j.detail.map((x: unknown) => (typeof x === "string" ? x : JSON.stringify(x))).join("; ");
    } catch {
      /* keep raw */
    }
    throw new Error(`GET /api/v1/logs/normalized failed (${res.status}): ${String(detail).slice(0, 800)}`.trim());
  }
  return (await res.json()) as NormalizedLogsS3Page;
}

export async function fetchNormalizedLogsFromDynamodb(
  params: { limit?: number; start_key?: string | null },
  options?: FetchNormalizedLogsDynamoOptions,
): Promise<NormalizedLogsDynamoPage> {
  const sp = new URLSearchParams();
  sp.set("limit", String(params.limit ?? 50));
  if (params.start_key?.trim()) sp.set("start_key", params.start_key.trim());
  const pk = options?.pk?.trim() || dynamoPkFromEnv();
  if (pk) sp.set("pk", pk);
  if (options?.region?.trim()) sp.set("region", options.region.trim());
  const q = sp.toString();
  const url = `${getApiUrl()}/api/v1/logs/dynamodb${q ? `?${q}` : ""}`;
  const res = await fetch(url, apiFetchInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = text;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail))
        detail = j.detail.map((x: unknown) => (typeof x === "string" ? x : JSON.stringify(x))).join("; ");
    } catch {
      /* keep raw */
    }
    throw new Error(`GET /api/v1/logs/dynamodb failed (${res.status}): ${String(detail).slice(0, 800)}`.trim());
  }
  return (await res.json()) as NormalizedLogsDynamoPage;
}

export type FetchSiemAnalyticsOptions = {
  since?: string;
  until?: string;
};

export async function fetchSiemAnalytics(hours: number = 24, options?: FetchSiemAnalyticsOptions): Promise<SiemDashboard> {
  const sp = new URLSearchParams();
  sp.set("hours", String(hours));
  const since = options?.since?.trim();
  const until = options?.until?.trim();
  if (since) sp.set("since", since);
  if (until) sp.set("until", until);
  const q = sp.toString();
  const url = `${getApiUrl()}/api/v1/analytics/siem?${q}`;
  const res = await fetch(url, apiFetchInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET /api/v1/analytics/siem failed (${res.status}) ${text}`.trim());
  }
  const j = (await res.json()) as SiemDashboard & { geo_logs?: SiemDashboard["geo_logs"] };
  return { ...j, geo_logs: Array.isArray(j.geo_logs) ? j.geo_logs : [] };
}

export type FetchDynamodbAnalyticsOptions = {
  pk?: string;
  region?: string;
  since?: string;
  until?: string;
  /** ``hour`` ou ``minute`` — agrégation UTC de la chronologie. */
  timelineGranularity?: "hour" | "minute";
};

/** Agrégations sur un échantillon DynamoDB (même ``pk`` / env que les logs). */
export async function fetchDynamodbAnalytics(
  maxItems: number = 15_000,
  options?: FetchDynamodbAnalyticsOptions,
): Promise<SiemDashboard> {
  const sp = new URLSearchParams();
  sp.set("max_items", String(maxItems));
  const pk = options?.pk?.trim() || dynamoPkFromEnv();
  if (pk) sp.set("pk", pk);
  if (options?.region?.trim()) sp.set("region", options.region.trim());
  const since = options?.since?.trim();
  const until = options?.until?.trim();
  if (since) sp.set("since", since);
  if (until) sp.set("until", until);
  const tg = options?.timelineGranularity;
  if (tg === "hour" || tg === "minute") sp.set("timeline_granularity", tg);
  const q = sp.toString();
  const url = `${getApiUrl()}/api/v1/analytics/dynamodb${q ? `?${q}` : ""}`;
  const res = await fetch(url, apiFetchInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = text;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* keep raw */
    }
    throw new Error(`GET /api/v1/analytics/dynamodb failed (${res.status}): ${String(detail).slice(0, 800)}`.trim());
  }
  const j = (await res.json()) as SiemDashboard & { geo_logs?: SiemDashboard["geo_logs"] };
  return { ...j, geo_logs: Array.isArray(j.geo_logs) ? j.geo_logs : [] };
}

/** Catalogue d’alertes SOC (jeu JSON côté API — même source que l’outil ``get_all_alerts``). */
export async function fetchAllAlerts(): Promise<AlertsCatalogResponse> {
  const url = `${getApiUrl()}/api/v1/alerts`;
  const res = await fetch(url, apiFetchInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = text;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* keep raw */
    }
    throw new Error(`GET /api/v1/alerts failed (${res.status}): ${String(detail).slice(0, 800)}`.trim());
  }
  return (await res.json()) as AlertsCatalogResponse;
}

// ---------------------------------------------------------------------------
// Agentic (SSE)
// ---------------------------------------------------------------------------

export type AgenticSsePayload = {
  type: string;
  data: Record<string, unknown>;
};

function parseSseBlocks(buffer: string): { events: AgenticSsePayload[]; rest: string } {
  const events: AgenticSsePayload[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    for (const line of block.split("\n")) {
      if (line.startsWith("data:")) {
        const json = line.slice(5).trimStart();
        if (!json) continue;
        try {
          events.push(JSON.parse(json) as AgenticSsePayload);
        } catch {
          /* ignore malformed chunk */
        }
      }
    }
  }
  return { events, rest };
}

export type ChatModelOption = {
  id: string;
  label: string;
  description: string;
};

export type ChatModelsResponse = {
  models: ChatModelOption[];
  default: string;
};

const CHAT_MODEL_STORAGE_KEY = "clair-obscur-chat-model";

export function loadStoredChatModel(): string | null {
  if (typeof window === "undefined") return null;
  const v = localStorage.getItem(CHAT_MODEL_STORAGE_KEY);
  return v?.trim() || null;
}

export function saveStoredChatModel(modelId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(CHAT_MODEL_STORAGE_KEY, modelId);
}

export async function fetchChatModels(): Promise<ChatModelsResponse> {
  const res = await fetch(`${getApiUrl()}/api/v1/agentic/models`, apiFetchInit);
  if (!res.ok) {
    throw new Error(`Chat models error ${res.status}`);
  }
  return res.json() as Promise<ChatModelsResponse>;
}

export async function streamAgenticChat(
  message: string,
  onEvent: (ev: AgenticSsePayload) => void,
  options?: { signal?: AbortSignal; conversationId?: string; model?: string },
): Promise<void> {
  const body: { message: string; conversation_id?: string; model?: string } = { message };
  if (options?.conversationId?.trim()) body.conversation_id = options.conversationId.trim();
  if (options?.model?.trim()) body.model = options.model.trim();

  const res = await fetch(`${getApiUrl()}/api/v1/agentic/stream`, {
    ...apiFetchInit,
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal: options?.signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Agentic stream error ${res.status}${text ? `: ${text.slice(0, 200)}` : ""}`.trim());
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseBlocks(buf);
    buf = rest;
    for (const ev of events) onEvent(ev);
  }

  if (buf.trim()) {
    const { events } = parseSseBlocks(buf + "\n\n");
    for (const ev of events) onEvent(ev);
  }
}

export async function submitAgenticApproval(
  conversationId: string,
  approvalId: string,
  approved: boolean,
): Promise<boolean> {
  const res = await fetch(`${getApiUrl()}/api/v1/agentic/approval`, {
    ...apiFetchInit,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId.trim(),
      approval_id: approvalId.trim(),
      approved,
    }),
  });
  let body: { ok?: boolean } = {};
  try {
    body = (await res.json()) as { ok?: boolean };
  } catch {
    /* ignore */
  }
  return Boolean(body.ok);
}

// ---------------------------------------------------------------------------
// Catalogue agents (paramètres UI)
// ---------------------------------------------------------------------------

export type CatalogToolInfo = {
  name: string;
  description: string;
  kind: string | null;
  parameters?: unknown;
  missing?: boolean;
};

export type SubagentCatalogEntry = {
  id: string;
  kind: "subagent";
  internal_name: string;
  description: string;
  prompt: string;
  tools: CatalogToolInfo[];
  max_turns: number;
  timeout_seconds: number;
};

export type PrincipalCatalogEntry = {
  id: string;
  kind: "principal";
  title: string;
  description: string;
  prompt: string;
  tools: CatalogToolInfo[];
};

export type AgentCatalogResponse = {
  principal: PrincipalCatalogEntry;
  subagents: SubagentCatalogEntry[];
};

export async function fetchAgentCatalog(): Promise<AgentCatalogResponse> {
  const base = getApiUrl();
  const paths = ["/api/v1/agentic/catalog", "/api/v1/agents/catalog"];
  let lastStatus = 0;
  let lastBody = "";
  for (const path of paths) {
    const res = await fetch(`${base}${path}`, {
      ...apiFetchInit,
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (res.ok) {
      return (await res.json()) as AgentCatalogResponse;
    }
    lastStatus = res.status;
    lastBody = await res.text().catch(() => "");
    if (res.status !== 404) {
      break;
    }
  }
  const hint =
    typeof window !== "undefined" &&
    (!base || base.startsWith("http://127.0.0.1") || base.startsWith("http://localhost"))
      ? " Vérifiez que l’API tourne (ex. uvicorn sur le port 8020) et que NEXT_PUBLIC_API_BASE pointe vers la bonne URL."
      : " Vérifiez NEXT_PUBLIC_API_BASE / déploiement de l’API (routes agentic ≥ version catalogue).";
  throw new Error(
    `Catalogue agents (${lastStatus})${lastBody ? `: ${lastBody.slice(0, 240)}` : ""}.${hint}`.trim(),
  );
}

export async function fetchVms(): Promise<VmsListResponse> {
  const url = `${getApiUrl()}/api/v1/vms`;
  const res = await fetch(url, apiFetchInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET /api/v1/vms failed (${res.status}): ${text.slice(0, 400)}`);
  }
  return (await res.json()) as VmsListResponse;
}

export async function approveVm(vmId: string): Promise<VmActionResponse> {
  const url = `${getApiUrl()}/api/v1/vms/${encodeURIComponent(vmId)}/approve`;
  const res = await fetch(url, { ...apiFetchInit, method: "POST" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Approbation échouée (${res.status}): ${text.slice(0, 400)}`);
  }
  return (await res.json()) as VmActionResponse;
}

export async function rejectVm(vmId: string): Promise<VmActionResponse> {
  const url = `${getApiUrl()}/api/v1/vms/${encodeURIComponent(vmId)}/reject`;
  const res = await fetch(url, { ...apiFetchInit, method: "POST" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Rejet échoué (${res.status}): ${text.slice(0, 400)}`);
  }
  return (await res.json()) as VmActionResponse;
}

export async function revokeVm(vmId: string): Promise<VmActionResponse> {
  const url = `${getApiUrl()}/api/v1/vms/${encodeURIComponent(vmId)}`;
  const res = await fetch(url, { ...apiFetchInit, method: "DELETE" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Révocation échouée (${res.status}): ${text.slice(0, 400)}`);
  }
  return (await res.json()) as VmActionResponse;
}
