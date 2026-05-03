import { autoTitleFromMessage, DEFAULT_SESSION_TITLE, generateSessionId, safeParseJson } from "@/lib/named-chat-sessions";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type ChatSessionPersisted = {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
};

const STORAGE_KEY = "clair-obscur-chat-sessions-v1";

const WELCOME_ASSISTANT: ChatMessage = {
  role: "assistant",
  content:
    "Bienvenue — je suis l’**assistant Clair Obscur** (supervision sécurité). Je peux t’aider sur les logs normalisés, les pratiques SOC et les scénarios de détection. Je n’ai **pas accès à tes données** : décris un contexte ou colle un extrait **anonymisé** si besoin.",
};

export function defaultSession(): ChatSessionPersisted {
  const id = generateSessionId();
  return {
    id,
    title: DEFAULT_SESSION_TITLE,
    updatedAt: Date.now(),
    messages: [WELCOME_ASSISTANT],
  };
}

export type ChatStoreState = {
  sessions: ChatSessionPersisted[];
  activeId: string;
};

export function loadChatStore(): ChatStoreState {
  if (typeof window === "undefined") {
    const s = defaultSession();
    return { sessions: [s], activeId: s.id };
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  const parsed = raw ? safeParseJson<ChatStoreState>(raw) : null;
  if (
    parsed &&
    Array.isArray(parsed.sessions) &&
    parsed.sessions.length > 0 &&
    typeof parsed.activeId === "string"
  ) {
    const sessions = parsed.sessions.filter(
      (x) => x && typeof x.id === "string" && Array.isArray(x.messages),
    ) as ChatSessionPersisted[];
    if (sessions.length === 0) {
      const s = defaultSession();
      return { sessions: [s], activeId: s.id };
    }
    const activeId = sessions.some((s) => s.id === parsed.activeId) ? parsed.activeId : sessions[0].id;
    return { sessions, activeId };
  }
  const s = defaultSession();
  return { sessions: [s], activeId: s.id };
}

export function saveChatStore(state: ChatStoreState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* quota / private mode */
  }
}

export function newSessionFromStore(state: ChatStoreState): ChatStoreState {
  const s = defaultSession();
  return {
    sessions: [s, ...state.sessions],
    activeId: s.id,
  };
}

export function renameSession(state: ChatStoreState, id: string, title: string): ChatStoreState {
  const t = title.trim() || DEFAULT_SESSION_TITLE;
  return {
    ...state,
    sessions: state.sessions.map((s) => (s.id === id ? { ...s, title: t, updatedAt: Date.now() } : s)),
  };
}

export function deleteSession(state: ChatStoreState, id: string): ChatStoreState {
  const rest = state.sessions.filter((s) => s.id !== id);
  if (rest.length === 0) {
    const s = defaultSession();
    return { sessions: [s], activeId: s.id };
  }
  const activeId = state.activeId === id ? rest[0].id : state.activeId;
  return { sessions: rest, activeId };
}

export function setActiveSession(state: ChatStoreState, id: string): ChatStoreState {
  if (!state.sessions.some((s) => s.id === id)) return state;
  return { ...state, activeId: id };
}

export function updateSessionMessages(
  state: ChatStoreState,
  id: string,
  messages: ChatMessage[],
  titleIfFirstUser?: string,
): ChatStoreState {
  return {
    ...state,
    sessions: state.sessions.map((s) => {
      if (s.id !== id) return s;
      const nextTitle =
        s.title === DEFAULT_SESSION_TITLE && titleIfFirstUser?.trim()
          ? autoTitleFromMessage(titleIfFirstUser)
          : s.title;
      return {
        ...s,
        messages,
        title: nextTitle,
        updatedAt: Date.now(),
      };
    }),
  };
}
