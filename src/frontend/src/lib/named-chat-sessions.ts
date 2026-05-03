export const DEFAULT_SESSION_TITLE = "Conversation";

export function generateSessionId(): string {
  const rand = Math.random().toString(16).slice(2);
  return `s_${Date.now().toString(16)}_${rand}`;
}

export function safeParseJson<T = unknown>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function autoTitleFromMessage(message: string): string {
  const s = (message || "").trim().replace(/\s+/g, " ");
  if (!s) return DEFAULT_SESSION_TITLE;
  return s.length > 48 ? `${s.slice(0, 48)}…` : s;
}

/** Garde le titre personnalisé ; sinon dérive depuis le premier message de la session. */
export function autoTitleFromSession(currentTitle: string, message: string): string {
  const t = (currentTitle || "").trim();
  if (t && t !== DEFAULT_SESSION_TITLE) return t;
  return autoTitleFromMessage(message);
}
