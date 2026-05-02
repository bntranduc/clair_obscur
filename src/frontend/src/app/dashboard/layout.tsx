"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ShieldAlert,
  Activity,
  Settings,
  Search,
  Bot,
  BookOpen,
  Ticket,
  Sparkles,
} from "lucide-react";
import UserMenu from "@/components/UserMenu";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      <aside className="sidebar-glass flex w-[17.5rem] shrink-0 flex-col">
        <div className="border-b border-white/[0.07] px-5 py-6">
          <Link href="/" className="group flex items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400/20 to-violet-500/25 ring-1 ring-white/10 transition group-hover:ring-cyan-400/30"
              aria-hidden
            >
              <span className="h-5 w-5 rounded-md bg-gradient-to-br from-cyan-300 to-violet-400 opacity-90" />
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
          <NavSection title="Données">
            <NavLink href="/dashboard/logs" icon={<Search size={18} strokeWidth={2} />} label="Logs normalisés" />
          </NavSection>

          <NavSection title="Monitoring">
            <NavLink href="/dashboard" icon={<ShieldAlert size={18} strokeWidth={2} />} label="Alertes" />
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
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-y-contain p-5 sm:p-6 lg:p-8">
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
  const active =
    href === "/dashboard"
      ? pathname === "/dashboard" || pathname.startsWith("/dashboard/alertes")
      : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors ${
        active
          ? "bg-cyan-500/[0.12] text-cyan-100 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.18)]"
          : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100"
      }`}
    >
      <span
        className={`flex shrink-0 transition-colors ${active ? "text-cyan-400" : "text-zinc-500 group-hover:text-zinc-300"}`}
      >
        {icon}
      </span>
      <span className="truncate">{label}</span>
      {active && (
        <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]" />
      )}
    </Link>
  );
}
