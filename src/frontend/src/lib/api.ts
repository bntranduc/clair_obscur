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
