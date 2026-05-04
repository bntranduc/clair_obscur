"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  Bot,
  ChevronRight,
  ExternalLink,
  Loader2,
  Sparkles,
  Wrench,
} from "lucide-react";
import {
  fetchAgentCatalog,
  type AgentCatalogResponse,
  type CatalogToolInfo,
  type SubagentCatalogEntry,
} from "@/lib/api";

const AGENT_ENV_ROWS: { name: string; hint: string }[] = [
  {
    name: "API_KEY, OPENROUTER_API_KEY ou LLM_API_KEY",
    hint: "Clé d’accès au fournisseur LLM (souvent OpenRouter). Requise pour l’assistant agentic.",
  },
  {
    name: "BASE_URL / OPENROUTER_BASE_URL",
    hint: "Point de terminaison compatible OpenAI (défaut OpenRouter : https://openrouter.ai/api/v1).",
  },
  {
    name: "AGENTIC_MAX_SESSIONS",
    hint: "Nombre maximal de sessions agentic en mémoire côté API (défaut 200).",
  },
  {
    name: "AGENTIC_MAX_TURNS",
    hint: "Plafond de tours (réponses + appels d’outils) par requête.",
  },
  {
    name: "AGENTIC_MAX_COMPLETION_TOKENS",
    hint: "Limite de tokens de sortie (0 = laisser le défaut).",
  },
  {
    name: "AGENTIC_STREAM_IDLE_SEC",
    hint: "Interruption du flux SSE si aucun chunk reçu pendant N secondes.",
  },
  {
    name: "AGENTIC_REASONING_EFFORT",
    hint: "Niveau de réflexion OpenRouter : off, low, medium, high, ou un entier.",
  },
  {
    name: "AGENTIC_REASONING_FORCE",
    hint: "Mettre à 1 pour forcer le bloc reasoning hors OpenRouter.",
  },
];

type SelectedAgent =
  | { type: "principal" }
  | { type: "subagent"; entry: SubagentCatalogEntry };

function ToolRow({ t }: { t: CatalogToolInfo }) {
  return (
    <li className="rounded-lg border border-white/[0.06] bg-black/25 px-3 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <code className="text-[13px] font-medium text-cyan-200/95">{t.name}</code>
        {t.kind ? (
          <span className="text-[10px] uppercase tracking-wide text-zinc-600">{t.kind}</span>
        ) : null}
        {t.missing ? (
          <span className="text-[11px] text-amber-400/90">référence manquante dans le registre</span>
        ) : null}
      </div>
      {t.description ? (
        <p className="mt-1.5 text-sm text-zinc-500 leading-relaxed">{t.description}</p>
      ) : null}
    </li>
  );
}

export default function AgentsCatalogPanel() {
  const [data, setData] = useState<AgentCatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SelectedAgent | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const c = await fetchAgentCatalog();
      setData(c);
      setSelected((prev) => {
        if (prev) return prev;
        return { type: "principal" };
      });
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "Impossible de charger le catalogue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20 text-zinc-500">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-500/80" aria-hidden />
        <p className="text-sm">Chargement du catalogue agents…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-950/25 px-4 py-4 text-sm text-red-200/95">
        <p>{error ?? "Erreur inconnue."}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-3 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/15"
        >
          Réessayer
        </button>
      </div>
    );
  }

  const principal = data.principal;
  const subagents = data.subagents;

  const detailTitle =
    selected?.type === "principal"
      ? principal.title
      : selected?.type === "subagent"
        ? selected.entry.id
        : principal.title;

  const detailDescription =
    selected?.type === "principal"
      ? principal.description
      : selected?.type === "subagent"
        ? selected.entry.description
        : principal.description;

  const detailPrompt =
    selected?.type === "principal"
      ? principal.prompt
      : selected?.type === "subagent"
        ? selected.entry.prompt
        : principal.prompt;

  const detailTools =
    selected?.type === "principal"
      ? principal.tools
      : selected?.type === "subagent"
        ? selected.entry.tools
        : principal.tools;

  return (
    <div className="space-y-8">
      <p className="text-[15px] leading-relaxed text-zinc-300">
        Sélectionnez un agent pour afficher sa description, son prompt système (ou objectif sous-agent) et la liste
        des outils exposés. Les données proviennent du registre côté API{" "}
        <code className="rounded bg-black/40 px-1.5 py-0.5 text-[13px] text-cyan-200/90">
          GET /api/v1/agentic/catalog
        </code>
        .
      </p>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <nav
          className="flex shrink-0 flex-col gap-1 rounded-xl border border-white/[0.08] bg-zinc-900/50 p-2 lg:w-[min(100%,280px)]"
          aria-label="Agents disponibles"
        >
          <button
            type="button"
            onClick={() => setSelected({ type: "principal" })}
            className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
              selected?.type === "principal"
                ? "bg-white/[0.12] text-white ring-1 ring-cyan-500/30"
                : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200"
            }`}
          >
            <Sparkles size={16} className="shrink-0 text-amber-400/90" aria-hidden />
            <span className="font-medium line-clamp-2">Agent principal</span>
          </button>
          {subagents.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setSelected({ type: "subagent", entry: s })}
              className={`flex items-start gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                selected?.type === "subagent" && selected.entry.id === s.id
                  ? "bg-white/[0.12] text-white ring-1 ring-violet-500/35"
                  : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200"
              }`}
            >
              <Bot size={16} className="mt-0.5 shrink-0 text-violet-400/90" aria-hidden />
              <span className="min-w-0">
                <span className="font-mono text-[12px] text-violet-200/90 break-all">{s.id}</span>
              </span>
            </button>
          ))}
        </nav>

        <div className="min-w-0 flex-1 space-y-5">
          <div>
            <h2 className="text-lg font-semibold text-white tracking-tight">{detailTitle}</h2>
            {selected?.type === "subagent" ? (
              <p className="mt-1 text-xs text-zinc-500 font-mono">
                Nom interne : {selected.entry.internal_name} · max {selected.entry.max_turns} tours · timeout{" "}
                {selected.entry.timeout_seconds}s
              </p>
            ) : null}
            <p className="mt-3 text-[15px] leading-relaxed text-zinc-400">{detailDescription}</p>
          </div>

          <section>
            <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              <ChevronRight size={14} className="text-cyan-500/80" aria-hidden />
              Prompt {selected?.type === "subagent" ? "(objectif & consignes sous-agent)" : "(système)"}
            </h3>
            <pre className="overflow-x-auto rounded-xl border border-white/[0.08] bg-black/40 p-4 text-[12px] leading-relaxed text-zinc-300 whitespace-pre-wrap break-words font-mono">
              {detailPrompt}
            </pre>
          </section>

          <section>
            <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              <Wrench size={14} className="text-amber-500/80" aria-hidden />
              Outils ({detailTools.length})
            </h3>
            <ul className="space-y-2">
              {detailTools.map((t, idx) => (
                <ToolRow key={`${t.name}-${idx}`} t={t} />
              ))}
            </ul>
          </section>
        </div>
      </div>

      <details className="group rounded-xl border border-white/[0.06] bg-zinc-900/35">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-zinc-400 transition hover:text-zinc-300 [&::-webkit-details-marker]:hidden">
          <span className="inline-flex items-center gap-2">
            <BookOpen size={16} className="text-cyan-500/80 shrink-0" aria-hidden />
            Configuration serveur (variables d’environnement)
            <span className="text-zinc-600 group-open:hidden">— afficher</span>
            <span className="hidden text-zinc-600 group-open:inline">— masquer</span>
          </span>
        </summary>
        <ul className="divide-y divide-white/[0.05] border-t border-white/[0.06]">
          {AGENT_ENV_ROWS.map((row) => (
            <li key={row.name} className="px-4 py-3.5 sm:px-5">
              <p className="font-mono text-[12px] sm:text-[13px] text-cyan-200/85 break-words">{row.name}</p>
              <p className="mt-1.5 text-sm text-zinc-500 leading-relaxed">{row.hint}</p>
            </li>
          ))}
        </ul>
      </details>

      <p className="text-xs text-zinc-600 flex items-start gap-2">
        <ExternalLink size={14} className="mt-0.5 shrink-0 text-zinc-500" aria-hidden />
        <span>
          Modifier le fichier <code className="text-zinc-500">.env</code> puis redémarrer l’API. Voir{" "}
          <code className="text-zinc-500">.env.example</code> (section Agentic).
        </span>
      </p>
    </div>
  );
}
