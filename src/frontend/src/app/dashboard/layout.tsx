import type { ReactNode } from "react";
import Link from "next/link";
import { Bell, FlaskConical, LayoutDashboard, MessageSquare, Search, Sparkles, Table2 } from "lucide-react";

export default function DashboardLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="min-h-screen bg-black text-zinc-100 flex">
      <aside className="w-56 shrink-0 glass-effect flex flex-col py-8 px-4 gap-2">
        <span className="text-xs uppercase tracking-widest text-zinc-500 px-3 mb-2">Menu</span>
        <NavLink href="/dashboard" icon={<LayoutDashboard size={18} />} label="Accueil" />
        <NavLink href="/dashboard/logs" icon={<Search size={18} />} label="Logs S3" />
        <NavLink href="/dashboard/events" icon={<Table2 size={18} />} label="Événements" />
        <NavLink href="/dashboard/test-model" icon={<FlaskConical size={18} />} label="Tester modèle" />
        <NavLink href="/dashboard/chat" icon={<MessageSquare size={18} />} label="Assistant Clair Obscur" />
        <NavLink href="/dashboard/incidents" icon={<Sparkles size={18} />} label="Incidents" />
        <NavLink href="/dashboard/alerts" icon={<Bell size={18} />} label="Alertes (JSON)" />
      </aside>
      <div className="flex-1 flex flex-col min-h-screen">
        <header className="border-b border-white/10 px-8 py-4 glass-panel">
          <Link href="/" className="text-sm text-zinc-400 hover:text-white transition-colors">
            ← Retour site
          </Link>
        </header>
        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}

function NavLink({
  href,
  icon,
  label,
}: {
  href: string;
  icon: ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-zinc-300 hover:bg-white/5 hover:text-white transition-colors"
    >
      <span className="text-zinc-500">{icon}</span>
      {label}
    </Link>
  );
}
