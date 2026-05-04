"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Home,
  LayoutDashboard,
  ShieldAlert,
  Settings,
  Search,
  Bot,
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  MessageCircle,
  Network,
} from "lucide-react";
import UserMenu from "@/components/UserMenu";
import AgenticChatAssistant from "@/components/dashboard/AgenticChatAssistant";

const SIDEBAR_LS_KEY = "clair-sidebar-nav-open";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isChatPage = pathname === "/dashboard/chat";
  const isClustersPage = pathname === "/dashboard/clusters";
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarReady, setSidebarReady] = useState(false);
  const [assistantSheetOpen, setAssistantSheetOpen] = useState(false);

  useEffect(() => {
    try {
      const v = localStorage.getItem(SIDEBAR_LS_KEY);
      if (v === "0") setSidebarOpen(false);
      if (v === "1") setSidebarOpen(true);
    } catch {
      /* ignore */
    }
    setSidebarReady(true);
  }, []);

  useEffect(() => {
    if (!sidebarReady) return;
    try {
      localStorage.setItem(SIDEBAR_LS_KEY, sidebarOpen ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [sidebarOpen, sidebarReady]);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((o) => !o);
  }, []);

  useEffect(() => {
    if (isChatPage) setAssistantSheetOpen(false);
  }, [isChatPage]);

  useEffect(() => {
    if (!assistantSheetOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAssistantSheetOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [assistantSheetOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      <div
        id="dashboard-sidebar"
        className={`relative shrink-0 overflow-hidden border-r border-white/[0.06] transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${
          sidebarOpen ? "w-[17.5rem]" : "w-12 border-white/[0.06]"
        }`}
      >
        <aside
          className={`sidebar-glass flex h-full flex-col ${sidebarOpen ? "w-[17.5rem]" : "w-12"}`}
        >
        {sidebarOpen ? (
          <>
        <div className="flex shrink-0 items-center gap-2 border-b border-white/[0.07] px-3 py-4">
          <Link href="/" className="group flex min-w-0 flex-1 items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-400/20 to-red-500/25 ring-1 ring-white/10 transition group-hover:ring-blue-400/30"
              aria-hidden
            >
              <span className="h-5 w-5 rounded-md bg-gradient-to-br from-blue-400 to-red-400 opacity-90" />
            </span>
            <div className="min-w-0">
              <span className="block truncate text-[15px] font-semibold tracking-tight text-white">
                CLAIR OBSCUR
              </span>
              <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">
                NDR Platform
              </span>
            </div>
          </Link>
          <button
            type="button"
            onClick={toggleSidebar}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/[0.1] bg-zinc-950/60 text-zinc-300 transition hover:border-blue-500/35 hover:bg-zinc-900/90 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
            aria-expanded={true}
            aria-controls="dashboard-sidebar"
            title="Masquer la navigation"
            aria-label="Masquer la navigation"
          >
            <ChevronsLeft size={20} strokeWidth={2} aria-hidden />
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4" aria-label="Navigation principale">
          <NavSection title="Vue d’ensemble">
            <NavLink href="/dashboard" icon={<Home size={18} strokeWidth={2} />} label="Accueil SOC" />
          </NavSection>

          <NavSection title="Monitoring">
            <NavLink href="/dashboard/alertes" icon={<ShieldAlert size={18} strokeWidth={2} />} label="Alertes" />
            <NavLink
              href="/dashboard/analytics"
              icon={<LayoutDashboard size={18} strokeWidth={2} />}
              label="Analytics"
            />
            <NavLink href="/dashboard/clusters" icon={<Network size={18} strokeWidth={2} />} label="Clusters" />
          </NavSection>

          <NavSection title="Données">
            <NavLink href="/dashboard/logs" icon={<Search size={18} strokeWidth={2} />} label="Logs" />
          </NavSection>

          <NavSection title="IA & docs">
            <NavLink href="/dashboard/chat" icon={<Bot size={18} strokeWidth={2} />} label="Assistant IA" />
            <NavLink href="/dashboard/wiki" icon={<BookOpen size={18} strokeWidth={2} />} label="Wiki" />
          </NavSection>

          <NavSection title="Système">
            <NavLink href="/dashboard/settings" icon={<Settings size={18} strokeWidth={2} />} label="Paramètres" />
          </NavSection>
        </nav>

        <div className="border-t border-white/[0.07] p-3">
          <UserMenu />
        </div>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center border-b border-white/[0.07] py-3">
            <button
              type="button"
              onClick={toggleSidebar}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/[0.1] bg-zinc-950/60 text-zinc-300 transition hover:border-blue-500/35 hover:bg-zinc-900/90 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
              aria-expanded={false}
              aria-controls="dashboard-sidebar"
              title="Afficher la navigation"
              aria-label="Afficher la navigation"
            >
              <ChevronsRight size={20} strokeWidth={2} aria-hidden />
            </button>
          </div>
        )}
        </aside>
      </div>

      <main className="app-main-bg relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="dashboard-aurora dashboard-aurora--a" />
          <div className="dashboard-aurora dashboard-aurora--b" />
          <div className="dashboard-aurora dashboard-aurora--c" />
        </div>
        <div className="dashboard-tactical-grid pointer-events-none absolute inset-0" aria-hidden />
        <div className="dashboard-tactical-sweep pointer-events-none absolute inset-0" aria-hidden />
        <div className="pointer-events-none absolute inset-0 grid-overlay" aria-hidden />
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            className={
              isChatPage
                ? "flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden overscroll-y-contain px-0 pb-0 pt-0"
                : isClustersPage
                  ? "flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden overscroll-y-contain px-0 pb-0 pt-0"
                  : "flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto overscroll-y-contain px-5 pb-5 pt-[2.125rem] sm:px-6 sm:pb-6 sm:pt-[2.25rem] lg:px-8 lg:pb-8 lg:pt-[2.375rem]"
            }
          >
            {children}
          </div>
        </div>

        {!isChatPage && !isClustersPage ? (
          <button
            type="button"
            onClick={() => setAssistantSheetOpen(true)}
            className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full border border-white/[0.14] bg-gradient-to-br from-blue-500 to-blue-700 text-white shadow-[0_8px_32px_-4px_rgba(37,99,235,0.55)] ring-1 ring-white/10 transition hover:scale-[1.04] hover:shadow-blue-500/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-400"
            title="Assistant IA"
            aria-label="Ouvrir l’assistant IA"
          >
            <MessageCircle size={26} strokeWidth={2} aria-hidden />
          </button>
        ) : null}

        {assistantSheetOpen ? (
          <div
            className="fixed inset-0 z-50 flex bg-black/50 backdrop-blur-[1px]"
            role="presentation"
            onClick={() => setAssistantSheetOpen(false)}
          >
            <div className="min-h-0 min-w-0 flex-1" aria-hidden />
            <div
              className="flex h-full min-h-0 w-full max-w-[min(100vw,40rem)] shrink-0 flex-col border-l border-white/[0.1] bg-zinc-950 shadow-2xl sm:max-w-[min(100vw,44rem)] md:max-w-[min(100vw,48rem)]"
              role="dialog"
              aria-modal="true"
              aria-labelledby="clair-assistant-sheet-title"
              onClick={(e) => e.stopPropagation()}
            >
              <span id="clair-assistant-sheet-title" className="sr-only">
                Assistant IA
              </span>
              <AgenticChatAssistant variant="overlay" onClose={() => setAssistantSheetOpen(false)} />
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}

function NavSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5 last:mb-2">
      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">{title}</p>
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}

function isNavLinkActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") {
    return pathname === "/dashboard";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const active = isNavLinkActive(pathname, href);

  return (
    <Link
      href={href}
      className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors ${
        active
          ? "bg-blue-500/[0.12] text-blue-100 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.2)]"
          : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100"
      }`}
    >
      <span
        className={`flex shrink-0 transition-colors ${active ? "text-blue-400" : "text-zinc-500 group-hover:text-zinc-300"}`}
      >
        {icon}
      </span>
      <span className="truncate">{label}</span>
      {active && (
        <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.55)]" />
      )}
    </Link>
  );
}
