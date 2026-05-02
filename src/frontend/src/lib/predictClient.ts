import { getModelPredictUrl } from "@/lib/modelPredict";

/** Même contrat que ``test_predict_http.py`` : ``POST /predict`` avec ``{ "events": [...] }`` → ``{ "alerts": [...] }``. */
export async function postPredict(events: Record<string, unknown>[]): Promise<{
  alerts: Record<string, unknown>[];
  rawText: string;
}> {
  const url = getModelPredictUrl();
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ events }),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${text.slice(0, 500)}`);
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Réponse non JSON.");
  }
  const list = (data as { alerts?: unknown }).alerts;
  if (!Array.isArray(list)) throw new Error("Réponse sans tableau alerts.");
  const alerts = list.filter(
    (x): x is Record<string, unknown> => Boolean(x) && typeof x === "object" && !Array.isArray(x)
  );
  return { alerts, rawText: text };
}
