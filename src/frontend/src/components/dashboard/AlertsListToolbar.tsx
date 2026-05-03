"use client";

import { LayoutGrid, Rows3 } from "lucide-react";

export type AlertsLayoutMode = "grid" | "row";

export default function AlertsListToolbar({
  mode,
  onModeChange,
}: {
  mode: AlertsLayoutMode;
  onModeChange: (m: AlertsLayoutMode) => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-xl border border-white/[0.08] bg-zinc-900/40 p-1">
      <button
        type="button"
        onClick={() => onModeChange("grid")}
        aria-pressed={mode === "grid"}
        title="Grille"
        className={`rounded-lg p-2 transition ${
          mode === "grid"
            ? "bg-white/[0.08] text-blue-200 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.22)]"
            : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300"
        }`}
      >
        <LayoutGrid size={18} strokeWidth={2} aria-hidden />
        <span className="sr-only">Affichage grille</span>
      </button>
      <button
        type="button"
        onClick={() => onModeChange("row")}
        aria-pressed={mode === "row"}
        title="Lignes"
        className={`rounded-lg p-2 transition ${
          mode === "row"
            ? "bg-white/[0.08] text-blue-200 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.22)]"
            : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300"
        }`}
      >
        <Rows3 size={18} strokeWidth={2} aria-hidden />
        <span className="sr-only">Affichage en ligne</span>
      </button>
    </div>
  );
}
