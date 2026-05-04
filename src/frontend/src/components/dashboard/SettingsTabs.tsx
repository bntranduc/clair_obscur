"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Bot, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import AgentsCatalogPanel from "@/components/dashboard/AgentsCatalogPanel";

type SettingsTab = "general" | "agents";
const LS_TAB = "clair-obscur-settings-tab";

function GeneralPanel() {
  return (
    <div className="space-y-6 text-[15px] leading-relaxed text-zinc-300">
      <p>
        Préférences globales du poste analyste. Les options liées à l’IA et aux outils de
        l’assistant sont regroupées dans l’onglet <span className="text-cyan-300/90">Agents</span>.
      </p>
      <div className="rounded-xl border border-dashed border-zinc-600/80 bg-zinc-900/35 px-5 py-6">
        <p className="text-sm text-zinc-500">
          D’autres réglages (thème, notifications, intégrations) pourront être branchés ici. Pour
          l’instant, utilisez le menu latéral et le profil utilisateur pour la navigation.
        </p>
        <Link
          href="/dashboard"
          className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-cyan-400/95 hover:text-cyan-300 transition-colors"
        >
          Retour à l’accueil SOC
        </Link>
      </div>
    </div>
  );
}

export default function SettingsTabs() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<SettingsTab>("general");

  useEffect(() => {
    const q = searchParams.get("tab");
    if (q === "agents") setTab("agents");
    else if (q === "general") setTab("general");
    else {
      try {
        const s = localStorage.getItem(LS_TAB);
        if (s === "agents" || s === "general") setTab(s);
      } catch {
        /* ignore */
      }
    }
  }, [searchParams]);

  const selectTab = useCallback((t: SettingsTab) => {
    setTab(t);
    try {
      localStorage.setItem(LS_TAB, t);
    } catch {
      /* ignore */
    }
    const url = new URL(window.location.href);
    url.searchParams.set("tab", t);
    window.history.replaceState(null, "", url.pathname + url.search);
  }, []);

  return (
    <div className="w-full min-w-0 max-w-none pb-10">
      <header className="border-b border-white/[0.06] pb-5">
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Paramètres</h1>
        <p className="mt-2 text-[15px] text-zinc-400">
          Préférences du dashboard et paramétrage de l’assistant agentic.
        </p>
      </header>

      <div
        role="tablist"
        aria-label="Sections paramètres"
        className="mt-5 flex flex-wrap gap-2 rounded-xl border border-white/[0.08] bg-zinc-900/45 p-1.5"
      >
        <button
          type="button"
          role="tab"
          id="tab-general"
          aria-selected={tab === "general"}
          aria-controls="panel-general"
          onClick={() => selectTab("general")}
          className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
            tab === "general"
              ? "bg-white/[0.12] text-white shadow-sm ring-1 ring-cyan-500/25"
              : "text-zinc-500 hover:bg-white/[0.05] hover:text-zinc-300"
          }`}
        >
          <SlidersHorizontal size={18} className="opacity-90 shrink-0" aria-hidden />
          Général
        </button>
        <button
          type="button"
          role="tab"
          id="tab-agents"
          aria-selected={tab === "agents"}
          aria-controls="panel-agents"
          onClick={() => selectTab("agents")}
          className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
            tab === "agents"
              ? "bg-white/[0.12] text-white shadow-sm ring-1 ring-cyan-500/25"
              : "text-zinc-500 hover:bg-white/[0.05] hover:text-zinc-300"
          }`}
        >
          <Bot size={18} className="opacity-90 shrink-0" aria-hidden />
          Agents
        </button>
      </div>

      <div className="mt-6">
        <div
          role="tabpanel"
          id="panel-general"
          aria-labelledby="tab-general"
          hidden={tab !== "general"}
          className={tab === "general" ? "dashboard-route-enter w-full max-w-none" : "hidden"}
        >
          {tab === "general" ? <GeneralPanel /> : null}
        </div>

        <div
          role="tabpanel"
          id="panel-agents"
          aria-labelledby="tab-agents"
          hidden={tab !== "agents"}
          className={tab === "agents" ? "dashboard-route-enter w-full max-w-none" : "hidden"}
        >
          {tab === "agents" ? <AgentsCatalogPanel /> : null}
        </div>
      </div>
    </div>
  );
}
