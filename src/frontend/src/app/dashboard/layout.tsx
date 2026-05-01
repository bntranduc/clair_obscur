"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, LayoutDashboard, Bell, FlaskConical, Cpu } from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-black text-white overflow-hidden">
      <aside className="w-56 border-r border-white/10 flex flex-col glass-effect shrink-0">
        <div className="p-4 border-b border-white/10">
          <Link href="/" className="text-lg font-bold hover:text-gray-300">
            CLAIR OBSCUR
          </Link>
          <p className="text-xs text-gray-500 mt-1">Dashboard</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <p className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Données
          </p>
          <NavLink href="/dashboard" icon={<LayoutDashboard size={18} />} label="Accueil" />
          <NavLink href="/dashboard/logs" icon={<Search size={18} />} label="Logs S3" />
          <p className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 mt-4">
            Modèle
          </p>
          <NavLink href="/dashboard/alerts" icon={<Bell size={18} />} label="Alertes" />
          <NavLink href="/dashboard/alerts-tmp" icon={<FlaskConical size={18} />} label="Alertes (TMP)" />
          <NavLink href="/dashboard/call-model" icon={<Cpu size={18} />} label="Appeler le modèle" />
        </nav>
      </aside>
      <main className="flex-1 overflow-auto bg-gradient-to-br from-black to-gray-950 relative">
        <div className="relative min-h-full">{children}</div>
      </main>
    </div>
  );
}

function navActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (pathname === href) return true;
  if (!pathname.startsWith(href)) return false;
  if (href === "/dashboard/alerts" && pathname.startsWith("/dashboard/alerts-tmp")) return false;
  if (href === "/dashboard/call-model") return pathname === "/dashboard/call-model";
  return pathname.startsWith(`${href}/`);
}

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const active = navActive(pathname, href);
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
        active ? "bg-white/10 text-white border-l-2 border-indigo-500" : "text-gray-400 hover:bg-white/5 hover:text-white"
      }`}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}
