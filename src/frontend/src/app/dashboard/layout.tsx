"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Home,
  LayoutDashboard,
  ShieldAlert,
  Activity,
  Settings,
  Search,
  Bot,
  BookOpen,
  Ticket,
  Sparkles,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import UserMenu from "@/components/UserMenu";

const SIDEBAR_LS_KEY = "clair-sidebar-nav-open";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarReady, setSidebarReady] = useState(false);

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

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      <div
        id="dashboard-sidebar"
        className={`relative shrink-0 overflow-hidden border-r border-white/[0.06] transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${
          sidebarOpen ? "w-[17.5rem]" : "w-0 border-transparent"
        }`}
        aria-hidden={!sidebarOpen}
      >
        <aside className="sidebar-glass flex h-full w-[17.5rem] flex-col">
        <div className="border-b border-white/[0.07] px-5 py-6">
          <Link href="/" className="group flex items-center gap-3">
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
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4">
          <NavSection title="Vue d’ensemble">
            <NavLink href="/dashboard" icon={<Home size={18} strokeWidth={2} />} label="Accueil SOC" />
          </NavSection>

          <NavSection title="Données">
            <NavLink href="/dashboard/logs" icon={<Search size={18} strokeWidth={2} />} label="Logs normalisés" />
          </NavSection>

          <NavSection title="Monitoring">
            <NavLink href="/dashboard/alertes" icon={<ShieldAlert size={18} strokeWidth={2} />} label="Alertes" />
            <NavLink
              href="/dashboard/analytics"
              icon={<LayoutDashboard size={18} strokeWidth={2} />}
              label="Analytics"
            />
            <NavLink href="/dashboard/network" icon={<Activity size={18} strokeWidth={2} />} label="Carte réseau" />
          </NavSection>

          <NavSection title="Incidents">
            <NavLink href="/dashboard/tickets" icon={<Ticket size={18} strokeWidth={2} />} label="Tickets" />
          </NavSection>

          <NavSection title="IA & docs">
            <NavLink href="/dashboard/chat" icon={<Bot size={18} strokeWidth={2} />} label="Assistant IA" />
            <NavLink href="/dashboard/agentic" icon={<Sparkles size={18} strokeWidth={2} />} label="Agentic" />
            <NavLink href="/dashboard/wiki" icon={<BookOpen size={18} strokeWidth={2} />} label="Wiki" />
          </NavSection>

          <NavSection title="Système">
            <NavLink href="/dashboard/settings" icon={<Settings size={18} strokeWidth={2} />} label="Paramètres" />
          </NavSection>
        </nav>

        <div className="border-t border-white/[0.07] p-3">
          <UserMenu />
        </div>
        </aside>
      </div>

      <main className="app-main-bg relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <button
          type="button"
          onClick={toggleSidebar}
          className="absolute left-4 top-4 z-30 flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.1] bg-zinc-950/85 text-zinc-300 shadow-lg shadow-black/30 backdrop-blur-md transition hover:border-blue-500/35 hover:bg-zinc-900/95 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          aria-expanded={sidebarOpen}
          aria-controls="dashboard-sidebar"
          title={sidebarOpen ? "Masquer la navigation" : "Afficher la navigation"}
        >
          {sidebarOpen ? <ChevronsLeft size={20} strokeWidth={2} aria-hidden /> : <ChevronsRight size={20} strokeWidth={2} aria-hidden />}
        </button>
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <div className="dashboard-aurora dashboard-aurora--a" />
          <div className="dashboard-aurora dashboard-aurora--b" />
          <div className="dashboard-aurora dashboard-aurora--c" />
        </div>
        <div className="dashboard-tactical-grid pointer-events-none absolute inset-0" aria-hidden />
        <div className="dashboard-tactical-sweep pointer-events-none absolute inset-0" aria-hidden />
        <div className="pointer-events-none absolute inset-0 grid-overlay" aria-hidden />
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-y-contain px-5 pb-5 pt-[4.25rem] sm:px-6 sm:pb-6 sm:pt-[4.5rem] lg:px-8 lg:pb-8 lg:pt-[4.75rem]">
            {children}
          </div>
        </div>
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

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);

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
