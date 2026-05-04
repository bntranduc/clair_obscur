"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  Sparkles,
  Wrench,
  ChevronDown,
  ChevronRight,
  Square,
  Brain,
  ListTree,
  ShieldAlert,
  X,
} from "lucide-react";
import { streamAgenticChat, submitAgenticApproval, type AgenticSsePayload } from "@/lib/api";
import { ChatSessionSidebar } from "@/components/dashboard/ChatSessionSidebar";
import { MarkdownMessage } from "@/components/dashboard/MarkdownMessage";
import { AgenticVizChart, parseAgenticChartPayload } from "@/components/dashboard/AgenticVizChart";
import {
  autoTitleFromSession,
  DEFAULT_SESSION_TITLE,
  generateSessionId,
  safeParseJson,
} from "@/lib/named-chat-sessions";

type ToolSegment = {
  kind: 'tool';
  callId: string;
  name: string;
  arguments: Record<string, unknown>;
  pending: boolean;
  success?: boolean;
  output?: string;
  error?: string;
  truncated?: boolean;
  /** Métadonnées outil (ex. ``chart`` pour visualization_from_prompt → Recharts). */
  metadata?: Record<string, unknown>;
  /** Présent si l’outil est invoqué depuis un sous-agent (streaming relayé). */
  subagent?: string;
  parentToolCallId?: string;
};

type TextSegment = {
  kind: 'text';
  content: string;
  streaming: boolean;
  /** Réponse texte du sous-agent (distincte du modèle principal). */
  subagent?: string;
};

/** Plan / résumé (ex. ``reasoning.summary`` OpenRouter) — bloc distinct style Cursor. */
type PlanningSegment = {
  kind: 'planning';
  content: string;
  streaming: boolean;
  turn?: number;
  /** Flux planning d’un sous-agent (ex. remediation_soc). */
  subagent?: string;
};

type PlanningArchiveSegment = {
  kind: 'planning_archive';
  content: string;
  turn: number;
  subagent?: string;
};

type ReasoningSegment = {
  kind: 'reasoning';
  content: string;
  streaming: boolean;
  /** Tour d’appel LLM (aligné sur `agent_step` phase llm). */
  turn?: number;
  subagent?: string;
};

/** Réflexion terminée d’un tour précédent — affichage repliable (style Cursor). */
type ReasoningArchiveSegment = {
  kind: 'reasoning_archive';
  content: string;
  turn: number;
  subagent?: string;
};

type StepSegment = {
  kind: 'step';
  phase: 'llm' | 'tools';
  turn: number;
};

/** Demande d’autorisation (SSE ``approval_required``) — juge de risque côté agentic. */
type PendingToolApproval = {
  approvalId: string;
  conversationId: string;
  toolName: string;
  description: string;
  paramsSummary: string;
  riskLevel?: string;
  riskRationale?: string;
  command?: string | null;
};

type RunSegment =
  | TextSegment
  | ToolSegment
  | PlanningSegment
  | PlanningArchiveSegment
  | ReasoningSegment
  | ReasoningArchiveSegment
  | StepSegment;

type AssistantRun = {
  segments: RunSegment[];
};

type UserMessage = { role: 'user'; content: string };
type AssistantMessage = { role: 'assistant'; run: AssistantRun };
type ChatRow = UserMessage | AssistantMessage;

type AgenticSession = {
  id: string;
  title: string;
  updatedAt: number;
  rows: ChatRow[];
};

type AgenticStore = {
  sessions: AgenticSession[];
  activeId: string;
};

const STORAGE_KEY = "clair-obscur-dashboard-agentic-v2";

type PersistedV1 = {
  v: 1;
  activeId: string;
  sessions: AgenticSession[];
};

function emptyAssistantRun(): AssistantRun {
  return { segments: [] };
}

function lastAgentStepSegment(segments: RunSegment[]): StepSegment | null {
  for (let i = segments.length - 1; i >= 0; i--) {
    const s = segments[i];
    if (s.kind === 'step') return s;
  }
  return null;
}

/** Affiche le bandeau « Réflexion… » pendant le tour LLM (avant/après deltas planning/reasoning), pas pendant exécution outils. */
function shouldShowReflexionBanner(segments: RunSegment[], isLiveStreaming: boolean): boolean {
  if (!isLiveStreaming) return false;
  const st = lastAgentStepSegment(segments);
  if (st?.phase === 'tools') return false;
  if (
    segments.some(
      (s) =>
        (s.kind === 'reasoning' || s.kind === 'planning') && s.streaming,
    )
  ) {
    return false;
  }
  const last = segments[segments.length - 1];
  if (last?.kind === 'text' && last.streaming) return false;
  if (last?.kind === 'tool' && last.pending) return false;
  return true;
}

function ReflexionStatusRow({ subtle }: { subtle?: boolean }) {
  return (
    <div
      className={
        subtle
          ? 'rounded-xl border border-cyan-500/20 bg-cyan-950/20 px-3 py-2.5'
          : 'rounded-2xl rounded-bl-md border border-cyan-500/30 bg-gradient-to-r from-cyan-950/45 via-zinc-900/55 to-blue-950/40 px-4 py-3 shadow-[0_0_24px_-8px_rgba(34,211,238,0.25)]'
      }
      role="status"
      aria-live="polite"
      aria-label="Réflexion en cours"
    >
      <div className="flex items-center gap-3">
        <Brain
          size={subtle ? 16 : 18}
          className="text-cyan-400 shrink-0 drop-shadow-[0_0_10px_rgba(34,211,238,0.35)]"
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-100 flex items-center gap-1.5 flex-wrap">
            <span>Réflexion</span>
            <span className="reflexion-dots inline-flex items-center translate-y-px" aria-hidden>
              <span />
              <span />
              <span />
            </span>
          </p>
          {!subtle ? (
            <div className="reflexion-shimmer-bar mt-2.5 w-full max-w-[min(100%,16rem)] opacity-95" />
          ) : (
            <div className="reflexion-shimmer-bar mt-2 h-[2px] w-full max-w-[12rem] opacity-70" />
          )}
        </div>
      </div>
    </div>
  );
}

const WELCOME_ROWS: ChatRow[] = [
  {
    role: 'assistant',
    run: {
      segments: [
        {
          kind: 'text',
          content:
            "Agent CLAIR OBSCUR : réponse en flux, réflexion du modèle (style Cursor) quand le LLM l’expose, étapes de boucle agent, traces d’outils. Posez une question sur les tickets ou la plateforme.",
          streaming: false,
        },
      ],
    },
  },
];

function createSession(): AgenticSession {
  return {
    id: generateSessionId(),
    title: DEFAULT_SESSION_TITLE,
    updatedAt: Date.now(),
    rows: [...WELCOME_ROWS],
  };
}

function loadStore(): AgenticStore {
  const raw =
    typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
  const p = safeParseJson<PersistedV1>(raw ?? '');
  if (p?.v === 1 && Array.isArray(p.sessions) && p.sessions.length > 0) {
    const activeId = p.sessions.some((s) => s.id === p.activeId) ? p.activeId : p.sessions[0].id;
    return { sessions: p.sessions, activeId };
  }
  const s = createSession();
  return { sessions: [s], activeId: s.id };
}

export type AgenticChatAssistantProps = {
  variant?: "page" | "overlay";
  onClose?: () => void;
};

export default function AgenticChatAssistant({ variant = "page", onClose }: AgenticChatAssistantProps) {
  const [store, setStore] = useState<AgenticStore | null>(null);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingToolApproval | null>(null);
  const [approvalSubmitting, setApprovalSubmitting] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Hydratation : état persistant localStorage après premier paint client.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement one-shot au montage
    setStore(loadStore());
  }, []);

  useEffect(() => {
    if (!store) return;
    const body: PersistedV1 = { v: 1, activeId: store.activeId, sessions: store.sessions };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(body));
  }, [store]);

  const activeSession = store?.sessions.find((s) => s.id === store?.activeId);
  const rows = useMemo(() => activeSession?.rows ?? [], [activeSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [rows, busy, store?.activeId]);

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    setPendingApproval(null);
  }, []);

  const submitApprovalDecision = useCallback(
    async (approved: boolean) => {
      if (!pendingApproval) return;
      setApprovalSubmitting(true);
      setStreamError(null);
      try {
        const ok = await submitAgenticApproval(
          pendingApproval.conversationId,
          pendingApproval.approvalId,
          approved
        );
        if (!ok) {
          setStreamError(
            "Réponse d’approbation non prise en compte (id invalide ou session expirée). Réessayez ou relancez le message."
          );
          return;
        }
        setPendingApproval(null);
      } finally {
        setApprovalSubmitting(false);
      }
    },
    [pendingApproval]
  );

  const handleEvent = useCallback((ev: AgenticSsePayload, draft: AssistantRun) => {
    const { type, data } = ev;

    const lastLlmTurn = (): number => {
      for (let i = draft.segments.length - 1; i >= 0; i--) {
        const s = draft.segments[i];
        if (s.kind === 'step' && s.phase === 'llm') return s.turn;
      }
      return 1;
    };

    if (type === 'agent_step') {
      const phase = data.phase === 'tools' ? 'tools' : 'llm';
      const turn = typeof data.turn === 'number' && data.turn >= 1 ? data.turn : 1;

      // Nouveau tour LLM : archiver plan + réflexion "live" du tour précédent (ardoise).
      if (phase === 'llm') {
        for (let i = draft.segments.length - 1; i >= 0; i--) {
          const s = draft.segments[i];
          if (s.kind === 'reasoning') {
            draft.segments[i] = {
              kind: 'reasoning_archive',
              content: s.content,
              turn: s.turn ?? turn - 1,
              subagent: s.subagent,
            };
            break;
          }
        }
        for (let i = draft.segments.length - 1; i >= 0; i--) {
          const s = draft.segments[i];
          if (s.kind === 'planning') {
            draft.segments[i] = {
              kind: 'planning_archive',
              content: s.content,
              turn: s.turn ?? turn - 1,
              subagent: s.subagent,
            };
            break;
          }
        }
      }

      draft.segments.push({ kind: 'step', phase, turn });
      return;
    }

    if (type === 'planning_delta' && typeof data.content === 'string') {
      const turn = lastLlmTurn();
      const sub = typeof data.subagent === 'string' ? data.subagent : undefined;
      const last = draft.segments[draft.segments.length - 1];
      const sameStream =
        last?.kind === 'planning' &&
        last.streaming &&
        (sub === undefined ? last.subagent === undefined : last.subagent === sub);
      if (sameStream) {
        last.content += data.content;
      } else {
        draft.segments.push({
          kind: 'planning',
          content: data.content,
          streaming: true,
          turn,
          subagent: sub,
        });
      }
      return;
    }

    if (type === 'planning_complete') {
      const full = typeof data.content === 'string' ? data.content : undefined;
      const sub = typeof data.subagent === 'string' ? data.subagent : undefined;
      let pIdx = -1;
      for (let i = draft.segments.length - 1; i >= 0; i--) {
        const seg = draft.segments[i];
        if (seg.kind === 'planning' && (sub === undefined ? seg.subagent === undefined : seg.subagent === sub)) {
          pIdx = i;
          break;
        }
      }
      if (pIdx >= 0) {
        const p = draft.segments[pIdx] as PlanningSegment;
        p.streaming = false;
        if (full !== undefined && full.length > 0) {
          p.content = full;
        }
      } else if (full !== undefined && full.length > 0) {
        draft.segments.push({
          kind: 'planning',
          content: full,
          streaming: false,
          turn: lastLlmTurn(),
          subagent: sub,
        });
      }
      return;
    }

    if (type === 'reasoning_delta' && typeof data.content === 'string') {
      const turn = lastLlmTurn();
      const sub = typeof data.subagent === 'string' ? data.subagent : undefined;
      const last = draft.segments[draft.segments.length - 1];
      const sameStream =
        last?.kind === 'reasoning' &&
        last.streaming &&
        (sub === undefined ? last.subagent === undefined : last.subagent === sub);
      if (sameStream) {
        last.content += data.content;
      } else {
        draft.segments.push({
          kind: 'reasoning',
          content: data.content,
          streaming: true,
          turn,
          subagent: sub,
        });
      }
      return;
    }

    if (type === 'reasoning_complete') {
      const full =
        typeof data.content === 'string' ? data.content : undefined;
      const sub = typeof data.subagent === 'string' ? data.subagent : undefined;
      let reasoningIdx = -1;
      for (let i = draft.segments.length - 1; i >= 0; i--) {
        const seg = draft.segments[i];
        if (seg.kind === 'reasoning' && (sub === undefined ? seg.subagent === undefined : seg.subagent === sub)) {
          reasoningIdx = i;
          break;
        }
      }
      if (reasoningIdx >= 0) {
        const r = draft.segments[reasoningIdx] as ReasoningSegment;
        r.streaming = false;
        if (full !== undefined && full.length > 0) {
          r.content = full;
        }
      } else if (full !== undefined && full.length > 0) {
        draft.segments.push({
          kind: 'reasoning',
          content: full,
          streaming: false,
          turn: lastLlmTurn(),
          subagent: sub,
        });
      }
      return;
    }

    if (type === 'text_delta' && typeof data.content === 'string') {
      const sub = typeof data.subagent === 'string' ? data.subagent : undefined;
      const last = draft.segments[draft.segments.length - 1];
      const sameStream =
        last?.kind === 'text' &&
        last.streaming &&
        (sub === undefined ? last.subagent === undefined : last.subagent === sub);
      if (sameStream) {
        last.content += data.content;
      } else {
        draft.segments.push({
          kind: 'text',
          content: data.content,
          streaming: true,
          subagent: sub,
        });
      }
      return;
    }

    if (type === 'text_complete' && typeof data.content === 'string') {
      const sub = typeof data.subagent === 'string' ? data.subagent : undefined;
      const last = draft.segments[draft.segments.length - 1];
      const sameStream =
        last?.kind === 'text' &&
        last.streaming &&
        (sub === undefined ? last.subagent === undefined : last.subagent === sub);
      if (sameStream) {
        last.content = data.content;
        last.streaming = false;
      } else {
        draft.segments.push({
          kind: 'text',
          content: data.content,
          streaming: false,
          subagent: sub,
        });
      }
      return;
    }

    if (type === 'tool_call_start') {
      draft.segments.push({
        kind: 'tool',
        callId: String(data.call_id ?? ''),
        name: String(data.name ?? ''),
        arguments: (data.arguments as Record<string, unknown>) ?? {},
        pending: true,
        subagent: typeof data.subagent === 'string' ? data.subagent : undefined,
        parentToolCallId:
          typeof data.parent_tool_call_id === 'string' ? data.parent_tool_call_id : undefined,
      });
      return;
    }

    if (type === 'tool_call_complete') {
      const id = String(data.call_id ?? '');
      const seg = draft.segments.find(
        (s): s is ToolSegment => s.kind === 'tool' && s.callId === id,
      );
      if (seg) {
        seg.pending = false;
        seg.success = Boolean(data.success);
        if (typeof data.output === 'string') seg.output = data.output;
        if (typeof data.error === 'string') seg.error = data.error;
        if (typeof data.truncated === 'boolean') seg.truncated = data.truncated;
        if (data.metadata !== undefined && data.metadata !== null && typeof data.metadata === 'object' && !Array.isArray(data.metadata)) {
          seg.metadata = data.metadata as Record<string, unknown>;
        }
      }
      return;
    }

    if (type === 'agent_error') {
      const msg = typeof data.error === 'string' ? data.error : 'Erreur agent';
      draft.segments.push({
        kind: 'text',
        content: `⚠️ ${msg}`,
        streaming: false,
      });
    }
  }, []);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || busy || !store) return;

    const sessionIdForTurn = store.activeId;
    const sess = store.sessions.find((s) => s.id === sessionIdForTurn);
    const nextTitle = sess ? autoTitleFromSession(sess.title, msg) : DEFAULT_SESSION_TITLE;

    setInput('');
    setStreamError(null);
    setPendingApproval(null);
    const userRow: UserMessage = { role: 'user', content: msg };
    const draftRun = emptyAssistantRun();
    const assistantPlaceholder: AssistantMessage = { role: 'assistant', run: draftRun };

    setStore((st) => {
      if (!st) return st;
      return {
        ...st,
        sessions: st.sessions.map((s) =>
          s.id === sessionIdForTurn
            ? {
                ...s,
                title: nextTitle,
                updatedAt: Date.now(),
                rows: [...s.rows, userRow, assistantPlaceholder],
              }
            : s,
        ),
      };
    });
    setBusy(true);

    const ac = new AbortController();
    abortRef.current = ac;

    const pushRowUpdate = () => {
      setStore((st) => {
        if (!st) return st;
        return {
          ...st,
          sessions: st.sessions.map((s) => {
            if (s.id !== sessionIdForTurn) return s;
            const prev = s.rows;
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') {
              next[next.length - 1] = {
                role: 'assistant',
                run: { segments: draftRun.segments.map((seg) => ({ ...seg })) },
              };
            }
            return { ...s, updatedAt: Date.now(), rows: next };
          }),
        };
      });
    };

    try {
      await streamAgenticChat(
        msg,
        (ev) => {
          if (ev.type === 'approval_required') {
            const d = ev.data;
            setPendingApproval({
              approvalId: String(d.approval_id ?? ''),
              conversationId: String(d.conversation_id ?? sessionIdForTurn),
              toolName: String(d.tool_name ?? ''),
              description: String(d.description ?? ''),
              paramsSummary: String(d.params_summary ?? ''),
              riskLevel: d.risk_level != null ? String(d.risk_level) : undefined,
              riskRationale: d.risk_rationale != null ? String(d.risk_rationale) : undefined,
              command: d.command != null ? String(d.command) : undefined,
            });
            return;
          }
          handleEvent(ev, draftRun);
          pushRowUpdate();
        },
        { signal: ac.signal, conversationId: sessionIdForTurn },
      );
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        draftRun.segments.push({
          kind: 'text',
          content: '— Interrompu.',
          streaming: false,
        });
      } else {
        const m = e instanceof Error ? e.message : String(e);
        setStreamError(m);
        draftRun.segments.push({
          kind: 'text',
          content: `⚠️ ${m}`,
          streaming: false,
        });
      }
      setStore((st) => {
        if (!st) return st;
        return {
          ...st,
          sessions: st.sessions.map((s) => {
            if (s.id !== sessionIdForTurn) return s;
            const prev = s.rows;
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') {
              next[next.length - 1] = {
                role: 'assistant',
                run: { segments: [...draftRun.segments] },
              };
            }
            return { ...s, updatedAt: Date.now(), rows: next };
          }),
        };
      });
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const lastRow = rows[rows.length - 1];
  const showStreamConnecting =
    busy && lastRow?.role === 'assistant' && lastRow.run.segments.length === 0;

  const startNewConversation = useCallback(() => {
    stopStream();
    setStreamError(null);
    const s = createSession();
    setStore((st) => {
      if (!st) return { sessions: [s], activeId: s.id };
      return { sessions: [s, ...st.sessions], activeId: s.id };
    });
    setInput('');
  }, [stopStream]);

  const selectSession = useCallback(
    (id: string) => {
      if (busy) return;
      stopStream();
      setStreamError(null);
      setStore((st) => (st ? { ...st, activeId: id } : st));
    },
    [busy, stopStream],
  );

  const renameSession = useCallback((id: string, title: string) => {
    const t = title.trim();
    if (!t) return;
    setStore((st) => {
      if (!st) return st;
      return {
        ...st,
        sessions: st.sessions.map((s) => (s.id === id ? { ...s, title: t, updatedAt: Date.now() } : s)),
      };
    });
  }, []);

  const deleteSession = useCallback((id: string) => {
    stopStream();
    setStreamError(null);
    setStore((st) => {
      if (!st) return st;
      const filtered = st.sessions.filter((s) => s.id !== id);
      const sessions = filtered.length ? filtered : [createSession()];
      const activeId = st.activeId === id ? sessions[0].id : st.activeId;
      return { sessions, activeId };
    });
  }, [stopStream]);

  if (!store || !activeSession) {
    return (
      <div
        className={
          variant === "page"
            ? "flex min-h-0 min-w-0 flex-1 w-full flex-col items-center justify-center overflow-hidden bg-zinc-950/50 text-sm text-gray-400"
            : "flex h-full min-h-[40vh] w-full flex-col items-center justify-center text-sm text-gray-400"
        }
      >
        Chargement des conversations…
      </div>
    );
  }

  const sidebarSessions = store.sessions.map(({ id, title, updatedAt }) => ({ id, title, updatedAt }));

  return (
    <div
      className={
        variant === "page"
          ? "relative flex min-h-0 min-w-0 w-full flex-1 flex-row overflow-hidden bg-zinc-950/55"
          : "relative flex h-full min-h-0 w-full max-w-full flex-row overflow-hidden rounded-none md:rounded-l-2xl"
      }
    >
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-20 flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.1] bg-zinc-900/90 text-zinc-300 transition hover:border-white/20 hover:bg-zinc-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          title="Fermer"
          aria-label="Fermer l’assistant"
        >
          <X size={18} strokeWidth={2} aria-hidden />
        </button>
      ) : null}
      <ChatSessionSidebar
        sessions={sidebarSessions}
        activeId={store.activeId}
        onSelect={selectSession}
        onNew={startNewConversation}
        onRename={renameSession}
        onDelete={deleteSession}
        disabled={busy}
      />
      <div
        className={
          variant === "page"
            ? "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-5 sm:px-7 lg:px-10"
            : "flex min-h-0 min-w-0 flex-1 flex-col"
        }
      >
        <div
          className={
            variant === "page"
              ? "border-b border-white/10 px-0 py-6 shrink-0"
              : "border-b border-white/10 p-6 shrink-0"
          }
        >
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles size={24} className="text-blue-400" />
            {activeSession.title}
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Flux SSE · réflexion / étapes de boucle · session ={' '}
            <code className="text-blue-300/90">conversation_id</code> (mémoire agentic). Les actions à risque élevé
            ouvrent une demande d’autorisation. Réflexion :
            OpenRouter (
            <code className="text-blue-300/80">AGENTIC_REASONING_EFFORT</code>, défaut <code className="text-blue-300/80">low</code>
            ).
          </p>
        </div>

        {streamError && (
          <div
            className={
              variant === "page"
                ? "mt-4 shrink-0 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300"
                : "mx-6 mt-4 shrink-0 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300"
            }
          >
            {streamError}
          </div>
        )}

        <div
          className={
            variant === "page"
              ? "dashboard-main-scroll min-h-0 flex-1 space-y-6 overscroll-y-contain px-0 py-6"
              : "min-h-0 flex-1 space-y-6 overflow-y-auto p-6"
          }
        >
          {rows.map((row, i) =>
            row.role === 'user' ? (
              <div key={i} className="flex gap-3 justify-end">
                <div className="max-w-[75%] rounded-2xl rounded-br-md border border-blue-800/35 bg-blue-950/65 px-4 py-3 text-sm whitespace-pre-wrap text-slate-200">
                  {row.content}
                </div>
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
                  <User size={16} className="text-gray-300" />
                </div>
              </div>
            ) : (
              <AssistantAnswerBlock
                key={i}
                run={row.run}
                isLiveStreaming={busy && i === rows.length - 1}
                showInlineReflexionBanner={
                  busy &&
                  i === rows.length - 1 &&
                  row.run.segments.length > 0 &&
                  shouldShowReflexionBanner(
                    row.run.segments,
                    busy && i === rows.length - 1,
                  )
                }
              />
            ),
          )}

          {showStreamConnecting && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot size={16} className="text-blue-400" />
              </div>
              <div className="min-w-0 flex-1 max-w-[85%]">
                <ReflexionStatusRow />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {pendingApproval && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-tool-title"
            className={
              variant === "page"
                ? "mb-3 shrink-0 rounded-xl border border-amber-400/45 bg-gradient-to-b from-amber-950/40 to-black/35 px-4 py-4 shadow-lg shadow-amber-900/20"
                : "mx-4 mb-3 shrink-0 rounded-xl border border-amber-400/45 bg-gradient-to-b from-amber-950/40 to-black/35 px-4 py-4 shadow-lg shadow-amber-900/20"
            }
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0">
                <ShieldAlert size={20} className="text-amber-300" />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <h2 id="approval-tool-title" className="text-sm font-semibold text-amber-100">
                  Autoriser cette action ?
                </h2>
                <p className="text-xs text-slate-400">
                  Un contrôle de criticité (plan + outil) a classé cette étape comme sensible. Le flux attend votre
                  décision (comme une confirmation Cursor).
                </p>
                <div className="text-sm text-slate-200">
                  <span className="text-amber-200/90 font-medium font-mono">
                    {pendingApproval.toolName || 'outil'}
                  </span>
                  {pendingApproval.riskLevel && (
                    <span className="ml-2 text-[11px] uppercase tracking-wide text-amber-400/90">
                      · {pendingApproval.riskLevel}
                    </span>
                  )}
                </div>
                {pendingApproval.riskRationale ? (
                  <p className="text-xs text-slate-300 leading-relaxed">{pendingApproval.riskRationale}</p>
                ) : null}
                <p className="text-xs text-slate-500">{pendingApproval.description}</p>
                {pendingApproval.command ? (
                  <pre className="text-[11px] text-slate-400 bg-black/35 rounded-lg p-2 border border-white/10 overflow-x-auto">
                    $ {pendingApproval.command}
                  </pre>
                ) : null}
                <pre className="text-[11px] text-slate-400 bg-black/35 rounded-lg p-2 border border-white/10 max-h-28 overflow-y-auto whitespace-pre-wrap font-mono">
                  {pendingApproval.paramsSummary || '—'}
                </pre>
                <div className="flex flex-wrap gap-2 pt-2">
                  <button
                    type="button"
                    disabled={approvalSubmitting || !pendingApproval.approvalId}
                    onClick={() => void submitApprovalDecision(true)}
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-40 transition-colors"
                  >
                    Autoriser
                  </button>
                  <button
                    type="button"
                    disabled={approvalSubmitting || !pendingApproval.approvalId}
                    onClick={() => void submitApprovalDecision(false)}
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-white/10 hover:bg-white/15 text-slate-100 border border-white/15 disabled:opacity-40 transition-colors"
                  >
                    Refuser
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <div
          className={
            variant === "page"
              ? "shrink-0 border-t border-white/10 px-0 py-4"
              : "shrink-0 border-t border-white/10 p-4"
          }
        >
          <div className="flex gap-3 items-end">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Question asynchrone (logs, snapshot plateforme, fichiers…)…"
              rows={2}
              disabled={busy}
              className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 resize-none disabled:opacity-50"
            />
            {busy ? (
              <button
                type="button"
                onClick={stopStream}
                className="p-3 bg-white/10 hover:bg-white/15 rounded-xl transition-colors text-white flex items-center gap-2"
                title="Arrêter"
              >
                <Square size={16} fill="currentColor" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!input.trim()}
                className="p-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 rounded-xl transition-colors"
              >
                <Send size={18} className="text-white" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function isTextSegment(seg: RunSegment): seg is TextSegment {
  return seg.kind === 'text';
}

/** Segments hors réponse finale du modèle principal (inclut planning/reasoning/outils + texte sous-agent). */
function reflectionSegmentCount(segments: RunSegment[]): number {
  return segments.filter((s) => {
    if (isTextSegment(s) && !s.subagent) return false;
    if (s.kind === 'step' && s.phase === 'llm') return false;
    return true;
  }).length;
}

function chartPayloadsFromRun(
  segments: RunSegment[],
): { key: string; payload: NonNullable<ReturnType<typeof parseAgenticChartPayload>> }[] {
  const out: { key: string; payload: NonNullable<ReturnType<typeof parseAgenticChartPayload>> }[] =
    [];
  for (const s of segments) {
    if (s.kind !== 'tool') continue;
    const p = parseAgenticChartPayload(s.metadata);
    if (p) out.push({ key: s.callId || `viz-${out.length}`, payload: p });
  }
  return out;
}

function RunSegmentBlock({ seg, j }: { seg: RunSegment; j: number }) {
  if (seg.kind === 'text') {
    if (seg.subagent) {
      return (
        <div className="rounded-2xl rounded-bl-md px-4 py-3 text-sm bg-violet-950/25 border border-violet-500/25 text-gray-200">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-300/90 mb-2">
            Sous-agent · {seg.subagent}
          </p>
          <MarkdownMessage content={seg.content} streaming={seg.streaming} />
        </div>
      );
    }
    return (
      <div className="rounded-2xl rounded-bl-md px-4 py-3 text-sm bg-white/5 border border-white/10 text-gray-200">
        <MarkdownMessage content={seg.content} streaming={seg.streaming} />
      </div>
    );
  }
  if (seg.kind === 'planning') {
    return <PlanningCard segment={seg} />;
  }
  if (seg.kind === 'planning_archive') {
    return <PlanningArchiveCard segment={seg} />;
  }
  if (seg.kind === 'reasoning') {
    return <ReasoningCard segment={seg} />;
  }
  if (seg.kind === 'reasoning_archive') {
    return <ReasoningArchiveCard segment={seg} />;
  }
  if (seg.kind === 'step') {
    if (seg.phase === 'llm') return null;
    return <StepCard segment={seg} />;
  }
  return <ToolCard tool={seg} />;
}

function AssistantAnswerBlock({
  run,
  isLiveStreaming,
  showInlineReflexionBanner,
}: {
  run: AssistantRun;
  isLiveStreaming: boolean;
  /** Bandeau « Réflexion… » pendant le tour LLM quand le flux n’a pas encore de bloc planning/reasoning actif. */
  showInlineReflexionBanner?: boolean;
}) {
  const [reflectionOpen, setReflectionOpen] = useState(isLiveStreaming);
  const prevLiveRef = useRef(isLiveStreaming);

  useEffect(() => {
    if (isLiveStreaming) setReflectionOpen(true);
    else if (prevLiveRef.current && !isLiveStreaming) setReflectionOpen(false);
    prevLiveRef.current = isLiveStreaming;
  }, [isLiveStreaming]);

  const nReflect = reflectionSegmentCount(run.segments);
  const hasReflection = nReflect > 0;
  const charts = chartPayloadsFromRun(run.segments);
  const textSegments = run.segments.filter(isTextSegment);

  const hideReflection = !reflectionOpen && !isLiveStreaming && hasReflection;

  return (
    <div className="flex gap-3 justify-start">
      <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-1">
        <Bot size={16} className="text-blue-400" />
      </div>
      <div className="max-w-[85%] min-w-0 flex-1 space-y-3">
        {showInlineReflexionBanner ? <ReflexionStatusRow subtle /> : null}
        {hideReflection ? (
          <>
            <button
              type="button"
              onClick={() => setReflectionOpen(true)}
              className="flex items-center gap-2 text-xs text-slate-400 hover:text-cyan-300/95 border border-white/10 hover:border-cyan-500/35 rounded-lg px-3 py-2 bg-white/[0.03] transition-colors w-full sm:w-auto text-left"
            >
              <ChevronRight size={14} className="text-cyan-500/80 shrink-0" />
              <Brain size={14} className="text-slate-500 shrink-0" />
              <span>
                Afficher la réflexion
                <span className="text-slate-600 ml-1">
                  ({nReflect === 1 ? '1 bloc masqué' : `${nReflect} blocs masqués`})
                </span>
              </span>
            </button>
            {textSegments.map((seg, j) => (
              <div
                key={`collapsed-text-${j}`}
                className="rounded-2xl rounded-bl-md px-4 py-3 text-sm bg-white/5 border border-white/10 text-gray-200"
              >
                <MarkdownMessage content={seg.content} streaming={seg.streaming} />
              </div>
            ))}
            {charts.map(({ key, payload }) => (
              <AgenticVizChart key={`collapsed-viz-${key}`} payload={payload} />
            ))}
          </>
        ) : (
          <>
            {run.segments.map((seg, j) => (
              <RunSegmentBlock key={`seg-${j}`} seg={seg} j={j} />
            ))}
            {!isLiveStreaming && hasReflection ? (
              <button
                type="button"
                onClick={() => setReflectionOpen(false)}
                className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300 border border-white/10 rounded-lg px-3 py-2 bg-white/[0.03] transition-colors w-full sm:w-auto text-left"
              >
                <ChevronDown size={14} className="text-slate-500 shrink-0" />
                <span>Masquer la réflexion</span>
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function StepCard({ segment }: { segment: StepSegment }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-400 border-l-2 border-blue-500/45 pl-3 py-2 bg-blue-500/5 rounded-r-lg">
      <ListTree size={14} className="text-blue-400 shrink-0" />
      <span className="font-medium text-blue-200/95 tracking-tight">
        Tour {segment.turn} — exécution des outils
      </span>
    </div>
  );
}

function PlanningArchiveCard({ segment }: { segment: PlanningArchiveSegment }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-blue-500/15 bg-blue-500/[0.04] overflow-hidden text-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-slate-500 hover:bg-white/5 text-xs"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <ListTree size={12} className="text-blue-500/80 shrink-0" />
        <span>
          Planning précédent · tour {segment.turn ?? '—'}
          {segment.subagent ? ` · ${segment.subagent}` : ''}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-2">
          <pre className="text-[11px] leading-relaxed text-slate-400 whitespace-pre-wrap font-mono bg-black/25 rounded-md p-2 border border-white/5 max-h-40 overflow-y-auto">
            {segment.content || '—'}
          </pre>
        </div>
      )}
    </div>
  );
}

function PlanningCard({ segment }: { segment: PlanningSegment }) {
  const [open, setOpen] = useState(true);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- rouvrir le panneau quand le flux planning repart
    if (segment.streaming) setOpen(true);
  }, [segment.streaming]);
  const turnLabel = segment.turn ?? "—";
  const waiting = !segment.content.trim() && segment.streaming;

  return (
    <div className="rounded-xl border border-blue-500/35 bg-gradient-to-b from-blue-950/35 to-black/20 overflow-hidden text-sm">
      <div className="px-3 pt-3 pb-2 border-b border-white/5">
        <div className="text-[13px] font-medium text-slate-100/95 flex items-center gap-2 flex-wrap">
          <ListTree size={15} className="text-blue-400 shrink-0" />
          <span>Planning</span>
          {segment.subagent ? (
            <span className="text-[10px] font-semibold uppercase tracking-wide text-violet-300/95 px-2 py-0.5 rounded-md bg-violet-500/15 border border-violet-500/25">
              sous-agent · {segment.subagent}
            </span>
          ) : null}
          {segment.streaming && (
            <Loader2 size={14} className="animate-spin text-blue-400/85 ml-auto shrink-0" />
          )}
        </div>
        <p className="text-xs text-slate-500 mt-1.5 pl-[1.35rem] leading-relaxed">
          {waiting ? (
            <span className="inline-flex items-center gap-2 flex-wrap">
              <span>
                Résumé / intention du modèle (tour {turnLabel})
              </span>
              <span className="reflexion-dots inline-flex items-center translate-y-px" aria-hidden>
                <span />
                <span />
                <span />
              </span>
            </span>
          ) : (
            `Plan ou résumé haut niveau (tour ${turnLabel}). Nouveau tour LLM → archivé ci‑dessous.`
          )}
        </p>
      </div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-slate-400 hover:bg-white/[0.04] text-xs"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-medium text-slate-400">Contenu</span>
      </button>
      {open && (
        <div className="px-3 pb-3">
          <pre className="text-xs leading-relaxed text-blue-100/90 whitespace-pre-wrap font-mono bg-black/45 rounded-lg p-3 border border-blue-500/15 max-h-56 overflow-y-auto">
            {segment.content || (waiting ? '…' : '')}
            {waiting && (
              <span className="inline-block w-1.5 h-3 ml-0.5 bg-blue-400 animate-pulse align-middle" />
            )}
          </pre>
        </div>
      )}
    </div>
  );
}

function ReasoningArchiveCard({ segment }: { segment: ReasoningArchiveSegment }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] overflow-hidden text-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-slate-500 hover:bg-white/5 text-xs"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Brain size={12} className="text-slate-500 shrink-0" />
        <span>
          Réflexion précédente · tour {segment.turn ?? '—'}
          {segment.subagent ? ` · ${segment.subagent}` : ''}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-2">
          <pre className="text-[11px] leading-relaxed text-slate-500 whitespace-pre-wrap font-mono bg-black/25 rounded-md p-2 border border-white/5 max-h-40 overflow-y-auto">
            {segment.content || '—'}
          </pre>
        </div>
      )}
    </div>
  );
}

function ReasoningCard({ segment }: { segment: ReasoningSegment }) {
  const [exploringOpen, setExploringOpen] = useState(true);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- rouvrir les détails pendant le streaming
    if (segment.streaming) setExploringOpen(true);
  }, [segment.streaming]);

  const waiting = !segment.content.trim() && segment.streaming;
  const turnLabel = segment.turn ?? '—';

  return (
    <div className="rounded-xl border border-cyan-500/25 bg-gradient-to-b from-cyan-950/30 to-black/20 overflow-hidden text-sm">
      <div className="px-3 pt-3 pb-2 border-b border-white/5 space-y-2">
        <div className="text-[13px] font-medium text-slate-200/95 flex items-center gap-2 flex-wrap">
          <Brain size={15} className="text-cyan-400 shrink-0" />
          <span className="text-slate-300">
            Réflexion{segment.subagent ? ` · ${segment.subagent}` : ''}
          </span>
          {segment.streaming && (
            <Loader2 size={14} className="animate-spin text-cyan-400/80 ml-auto shrink-0" />
          )}
        </div>
        <p className="text-xs text-slate-500 leading-relaxed pl-[1.4rem]">
          {waiting ? (
            <span className="inline-flex items-center gap-2 flex-wrap">
              <span>Mise en forme du raisonnement détaillé</span>
              <span className="reflexion-dots inline-flex items-center translate-y-px" aria-hidden>
                <span />
                <span />
                <span />
              </span>
            </span>
          ) : (
            `Raisonnement en direct (tour ${turnLabel}). Nouveau tour LLM → ce bloc est archivé et repart vide.`
          )}
        </p>
      </div>
      <button
        type="button"
        onClick={() => setExploringOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-slate-400 hover:bg-white/[0.04] text-xs"
      >
        {exploringOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-medium text-slate-400">Détails</span>
        <span className="text-slate-600">· tour {segment.turn ?? '—'}</span>
      </button>
      {exploringOpen && (
        <div className="px-3 pb-3">
          <pre className="text-xs leading-relaxed text-slate-300 whitespace-pre-wrap font-mono bg-black/40 rounded-lg p-3 border border-white/[0.06] max-h-72 overflow-y-auto">
            {segment.content || (segment.streaming ? '…' : '')}
            {segment.streaming && (
              <span className="inline-block w-1.5 h-3 ml-0.5 bg-cyan-400 animate-pulse align-middle" />
            )}
          </pre>
        </div>
      )}
    </div>
  );
}

function ToolCard({ tool }: { tool: ToolSegment }) {
  const [open, setOpen] = useState(true);
  const vizPayload =
    tool.name === "visualization_from_prompt" && tool.success !== false
      ? parseAgenticChartPayload(tool.metadata)
      : null;

  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 overflow-hidden text-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-amber-200/90 hover:bg-white/5"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <Wrench size={14} className="text-amber-400 shrink-0" />
        <span className="font-medium">{tool.name || 'tool'}</span>
        {tool.subagent ? (
          <span className="text-[10px] font-medium text-violet-300/90 px-1.5 py-0.5 rounded bg-violet-500/10 border border-violet-500/20 shrink-0">
            via {tool.subagent}
          </span>
        ) : null}
        {tool.pending ? (
          <Loader2 size={14} className="animate-spin text-amber-400 ml-auto" />
        ) : tool.success ? (
          <span className="ml-auto text-xs text-green-400/90">ok</span>
        ) : (
          <span className="ml-auto text-xs text-red-400/90">échec</span>
        )}
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-3 text-gray-400">
          <pre className="text-xs bg-black/40 rounded-lg p-2 overflow-x-auto max-h-32 overflow-y-auto border border-white/5">
            {JSON.stringify(tool.arguments, null, 2)}
          </pre>
          {tool.error && <p className="text-xs text-red-400">{tool.error}</p>}
          {vizPayload ? (
            <AgenticVizChart payload={vizPayload} />
          ) : null}
          {tool.output != null &&
            (vizPayload ? (
              <details className="group">
                <summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-400 mb-2">
                  Sortie texte / ASCII (optionnel)
                </summary>
                <pre className="text-xs bg-black/40 rounded-lg p-2 overflow-x-auto max-h-48 overflow-y-auto border border-white/5 whitespace-pre-wrap">
                  {tool.output}
                  {tool.truncated ? '\n…' : ''}
                </pre>
              </details>
            ) : (
              <pre className="text-xs bg-black/40 rounded-lg p-2 overflow-x-auto max-h-48 overflow-y-auto border border-white/5 whitespace-pre-wrap">
                {tool.output}
                {tool.truncated ? '\n…' : ''}
              </pre>
            ))}
        </div>
      )}
    </div>
  );
}
