import type { NormalizedEvent } from "@/lib/normalizedLog";
import type { SiemDashboard } from "@/types/siemAnalytics";

const DEFAULT_API_URL = "http://127.0.0.1:8020";

function getApiUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
  return raw.replace(/\/+$/, "");
}

export type NormalizedLogsPage = {
  items: NormalizedEvent[];
  has_more: boolean;
  skip: number;
  limit: number;
};

export async function fetchNormalizedLogs(params: {
  skip?: number;
  limit?: number;
}): Promise<NormalizedLogsPage> {
  const sp = new URLSearchParams();
  if (params.skip !== undefined) sp.set("skip", String(params.skip));
  if (params.limit !== undefined) sp.set("limit", String(params.limit));
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

/** Assistant IA (Bedrock) — même route sur ``api.main`` (8020) et ``api.model_app`` (8080). */
export async function postChat(messages: ChatApiMessage[]): Promise<ChatApiResponse> {
  const url = `${getApiUrl()}/api/v1/chat`;
  const trimmed = messages.slice(-24);
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: trimmed }),
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
