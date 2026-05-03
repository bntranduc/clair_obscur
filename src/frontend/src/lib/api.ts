import type { NormalizedEvent } from "@/lib/normalizedLog";
import type { SiemDashboard } from "@/types/siemAnalytics";

/** API FastAPI déployée (EC2). */
const API_BASE_URL = "http://13.39.106.74:8020";

function getApiUrl(): string {
  return API_BASE_URL.replace(/\/+$/, "");
}

/** Query optionnelle pour ``GET /api/v1/logs/normalized`` (identifiants = mêmes noms que les variables AWS). */
export type FetchNormalizedLogsOptions = {
  raw_logs_bucket?: string;
  raw_logs_prefix?: string;
  region?: string;
  /** Équivalent query ``AWS_ACCESS_KEY_ID`` (ne pas utiliser côté navigateur en prod). */
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_session_token?: string;
};

export type NormalizedLogsPage = {
  items: NormalizedEvent[];
  has_more: boolean;
  skip: number;
  limit: number;
};

export async function fetchNormalizedLogs(
  params: { skip?: number; limit?: number },
  options?: FetchNormalizedLogsOptions,
): Promise<NormalizedLogsPage> {
  const sp = new URLSearchParams();
  sp.set("skip", String(params.skip ?? 0));
  sp.set("limit", String(params.limit ?? 50));
  if (options?.raw_logs_bucket?.trim()) sp.set("raw_logs_bucket", options.raw_logs_bucket.trim());
  if (options?.raw_logs_prefix?.trim()) sp.set("raw_logs_prefix", options.raw_logs_prefix.trim());
  if (options?.region?.trim()) sp.set("region", options.region.trim());
  const ak = options?.aws_access_key_id?.trim();
  const sk = options?.aws_secret_access_key?.trim();
  const st = options?.aws_session_token?.trim();
  if (ak && sk) {
    sp.set("AWS_ACCESS_KEY_ID", ak);
    sp.set("AWS_SECRET_ACCESS_KEY", sk);
    if (st) sp.set("AWS_SESSION_TOKEN", st);
  }

  const q = sp.toString();
  const url = `${getApiUrl()}/api/v1/logs/normalized${q ? `?${q}` : ""}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET /api/v1/logs/normalized failed (${res.status}) ${text}`.trim());
  }
  return (await res.json()) as NormalizedLogsPage;
}

export async function fetchSiemAnalytics(hours: number = 24): Promise<SiemDashboard> {
  const url = `${getApiUrl()}/api/v1/analytics/siem?hours=${encodeURIComponent(String(hours))}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET /api/v1/analytics/siem failed (${res.status}) ${text}`.trim());
  }
  return (await res.json()) as SiemDashboard;
}

export type ChatApiMessage = { role: "user" | "assistant"; content: string };

export type ChatApiResponse = { reply: string };

export type PostChatOptions = {
  region?: string;
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_session_token?: string;
};

/** Assistant IA (Bedrock) — ``POST /api/v1/chat`` sur l’API EC2. Identifiants optionnels (déconseillé côté navigateur). */
export async function postChat(messages: ChatApiMessage[], options?: PostChatOptions): Promise<ChatApiResponse> {
  const url = `${getApiUrl()}/api/v1/chat`;
  const trimmed = messages.slice(-24);
  const payload: Record<string, unknown> = { messages: trimmed };
  if (options?.region?.trim()) payload.region = options.region.trim();
  const ak = options?.aws_access_key_id?.trim();
  const sk = options?.aws_secret_access_key?.trim();
  const st = options?.aws_session_token?.trim();
  if (ak && sk) {
    payload.aws_access_key_id = ak;
    payload.aws_secret_access_key = sk;
    if (st) payload.aws_session_token = st;
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
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
    throw new Error(`POST /api/v1/chat failed (${res.status}): ${String(detail).slice(0, 600)}`.trim());
  }
  return (await res.json()) as ChatApiResponse;
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

export async function streamAgenticChat(
  message: string,
  onEvent: (ev: AgenticSsePayload) => void,
  options?: { signal?: AbortSignal; conversationId?: string },
): Promise<void> {
  const body: { message: string; conversation_id?: string } = { message };
  if (options?.conversationId?.trim()) body.conversation_id = options.conversationId.trim();

  const res = await fetch(`${getApiUrl()}/api/v1/agentic/stream`, {
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
