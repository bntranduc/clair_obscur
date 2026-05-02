"use client";

import Link from "next/link";
import { User, ChevronDown } from "lucide-react";
import { useRef, useState, useEffect } from "react";

export default function UserMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="focus-ring flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.04]"
        aria-expanded={open}
        aria-haspopup="true"
      >
        <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 text-sm font-semibold text-white ring-2 ring-zinc-600/50 ring-offset-2 ring-offset-zinc-950">
          ?
        </span>
        <div className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-zinc-100">Analyste</span>
          <span className="block truncate text-[11px] text-zinc-500">Session locale</span>
        </div>
        <ChevronDown
          size={16}
          className={`shrink-0 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-white/[0.08] bg-zinc-900/95 py-1 shadow-2xl shadow-black/50 backdrop-blur-xl"
          role="menu"
        >
          <Link
            href="/dashboard/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2.5 text-sm text-zinc-300 transition-colors hover:bg-white/[0.06] hover:text-white"
            role="menuitem"
          >
            <User size={16} className="text-zinc-500" />
            Profil
          </Link>
        </div>
      )}
    </div>
  );
}
