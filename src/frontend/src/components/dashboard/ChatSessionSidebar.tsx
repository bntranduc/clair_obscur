"use client";

import { useCallback, useState } from "react";
import { MessageSquarePlus, Pencil, Trash2, Check, X } from "lucide-react";

export type SessionSidebarEntry = {
  id: string;
  title: string;
  updatedAt: number;
};

type ChatSessionSidebarProps = {
  sessions: SessionSidebarEntry[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  disabled?: boolean;
  className?: string;
};

export function ChatSessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
  disabled = false,
  className = "",
}: ChatSessionSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");

  const startEdit = useCallback((e: React.MouseEvent, s: SessionSidebarEntry) => {
    e.stopPropagation();
    setEditingId(s.id);
    setDraftTitle(s.title);
  }, []);

  const commitEdit = useCallback(() => {
    if (!editingId) return;
    const t = draftTitle.trim();
    if (!t) return;
    onRename(editingId, t);
    setEditingId(null);
    setDraftTitle("");
  }, [draftTitle, editingId, onRename]);

  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setDraftTitle("");
  }, []);

  const sorted = [...sessions].sort((x, y) => y.updatedAt - x.updatedAt);

  return (
    <aside
      className={`flex h-full max-h-44 min-h-0 w-full shrink-0 flex-col border-b border-white/[0.08] bg-zinc-950/50 lg:max-h-none lg:w-[260px] lg:border-b-0 lg:border-r ${className}`.trim()}
    >
      <div className="shrink-0 border-b border-white/[0.08] p-3">
        <button
          type="button"
          onClick={onNew}
          disabled={disabled}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.1] py-2.5 text-sm font-medium text-blue-200 transition hover:border-blue-500/30 hover:bg-blue-500/10 disabled:opacity-40"
        >
          <MessageSquarePlus size={18} />
          Nouvelle conversation
        </button>
      </div>
      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {sorted.map((s) => {
          const isActive = s.id === activeId;
          return (
            <div
              key={s.id}
              role="button"
              tabIndex={0}
              onClick={() => !disabled && onSelect(s.id)}
              onKeyDown={(ev) => {
                if (disabled) return;
                if (ev.key === "Enter" || ev.key === " ") {
                  ev.preventDefault();
                  onSelect(s.id);
                }
              }}
              className={`group cursor-pointer rounded-xl border border-transparent px-2 py-2 text-left transition-colors ${
                isActive
                  ? "border-blue-500/35 bg-blue-500/15 text-white"
                  : "text-zinc-400 hover:bg-white/[0.04]"
              } ${disabled ? "pointer-events-none opacity-40" : ""}`}
            >
              {editingId === s.id ? (
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  <input
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitEdit();
                      if (e.key === "Escape") cancelEdit();
                    }}
                    className="min-w-0 flex-1 rounded border border-white/15 bg-black/40 px-2 py-1 text-xs text-white focus:border-white/30 focus:outline-none"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={commitEdit}
                    className="rounded p-1 text-emerald-400 hover:bg-white/10"
                    aria-label="Valider"
                  >
                    <Check size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={cancelEdit}
                    className="rounded p-1 text-zinc-400 hover:bg-white/10"
                    aria-label="Annuler"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="flex items-start gap-1">
                  <span className="line-clamp-2 min-w-0 flex-1 break-words text-sm leading-snug">{s.title}</span>
                  <div className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={(e) => startEdit(e, s)}
                      disabled={disabled}
                      className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white disabled:opacity-30"
                      aria-label="Renommer"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!disabled) onDelete(s.id);
                      }}
                      disabled={disabled}
                      className="rounded p-1 text-zinc-400 hover:bg-red-500/15 hover:text-red-300 disabled:opacity-30"
                      aria-label="Supprimer"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
