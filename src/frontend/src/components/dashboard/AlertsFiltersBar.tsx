"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, FilterX } from "lucide-react";
import type { SeverityLevel } from "@/types/modelPrediction";
import { attackDisplayName } from "@/lib/attackLabels";
import type { AlertsFilterState } from "@/lib/filterAlerts";
import { defaultAlertsFilterState } from "@/lib/filterAlerts";

const SEVERITY_OPTIONS: { value: "" | SeverityLevel; label: string }[] = [
  { value: "", label: "Toutes criticités" },
  { value: "low", label: "Faible" },
  { value: "medium", label: "Moyenne" },
  { value: "high", label: "Élevée" },
  { value: "critical", label: "Critique" },
];

function matchesAttackSearch(typeId: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const label = attackDisplayName(typeId).toLowerCase();
  const id = typeId.toLowerCase().replace(/_/g, " ");
  return label.includes(q) || typeId.toLowerCase().includes(q) || id.includes(q);
}

function AttackTypeCombobox({
  value,
  attackTypes,
  onSelect,
}: {
  value: string;
  attackTypes: string[];
  onSelect: (attackType: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(() =>
    value ? attackDisplayName(value) : "",
  );
  const [highlight, setHighlight] = useState(0);

  useEffect(() => {
    setDraft(value ? attackDisplayName(value) : "");
  }, [value]);

  const filtered = useMemo(
    () => attackTypes.filter((t) => matchesAttackSearch(t, draft)),
    [attackTypes, draft],
  );

  const listItems = useMemo(() => {
    const rows: { key: string; typeId: string | null; label: string }[] = [
      { key: "__all", typeId: null, label: "Tous les types" },
      ...filtered.map((t) => ({
        key: t,
        typeId: t,
        label: attackDisplayName(t),
      })),
    ];
    return rows;
  }, [filtered]);

  useEffect(() => {
    setHighlight((h) => Math.min(h, Math.max(0, listItems.length - 1)));
  }, [listItems.length]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const pick = useCallback(
    (typeId: string | null) => {
      onSelect(typeId ?? "");
      setDraft(typeId ? attackDisplayName(typeId) : "");
      setOpen(false);
      inputRef.current?.blur();
    },
    [onSelect],
  );

  const onInputChange = (next: string) => {
    setDraft(next);
    setOpen(true);
    setHighlight(0);
    if (value && next.trim() !== attackDisplayName(value).trim()) {
      onSelect("");
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      setOpen(true);
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setDraft(value ? attackDisplayName(value) : "");
      return;
    }
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => (h + 1) % listItems.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => (h - 1 + listItems.length) % listItems.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const row = listItems[highlight];
      if (row) pick(row.typeId);
    }
  };

  return (
    <div ref={wrapRef} className="relative min-w-[12rem] flex-1">
      <div className="relative">
        <input
          ref={inputRef}
          id="alert-filter-type"
          type="search"
          role="combobox"
          aria-expanded={open}
          aria-controls="attack-type-listbox"
          aria-autocomplete="list"
          autoComplete="off"
          placeholder="Rechercher un type d’attaque…"
          value={draft}
          onChange={(e) => onInputChange(e.target.value)}
          onFocus={() => {
            setOpen(true);
            setHighlight(0);
          }}
          onKeyDown={onKeyDown}
          className="w-full rounded-lg border border-white/10 bg-black/40 py-2 pl-3 pr-9 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30"
        />
        <ChevronDown
          size={16}
          className={`pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 transition ${open ? "rotate-180" : ""}`}
          aria-hidden
        />
      </div>
      {open ? (
        <ul
          id="attack-type-listbox"
          role="listbox"
          className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-white/12 bg-zinc-950 py-1 shadow-xl shadow-black/50"
        >
          {listItems.map((row, i) => (
            <li
              key={row.key}
              role="option"
              aria-selected={i === highlight}
              className={`cursor-pointer px-3 py-2 text-sm ${
                i === highlight ? "bg-blue-500/20 text-blue-100" : "text-zinc-200 hover:bg-white/[0.06]"
              }`}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={(ev) => {
                ev.preventDefault();
                pick(row.typeId);
              }}
            >
              {row.typeId ? (
                <span className="flex flex-col gap-0.5">
                  <span>{row.label}</span>
                  <span className="font-mono text-[10px] text-zinc-500">{row.typeId}</span>
                </span>
              ) : (
                <span className="text-zinc-400">{row.label}</span>
              )}
            </li>
          ))}
          {draft.trim() && filtered.length === 0 ? (
            <li className="pointer-events-none px-3 py-2 text-xs text-zinc-500 border-t border-white/[0.06]">
              Aucun identifiant technique ne correspond — vous pouvez choisir « Tous les types » ou affiner la saisie.
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}

export default function AlertsFiltersBar({
  filter,
  attackTypes,
  onChange,
}: {
  filter: AlertsFilterState;
  attackTypes: string[];
  onChange: (next: AlertsFilterState) => void;
}) {
  const active =
    Boolean(filter.attackType) ||
    Boolean(filter.severity) ||
    Boolean(filter.dateFrom) ||
    Boolean(filter.dateTo);

  return (
    <div className="rounded-xl border border-white/[0.08] bg-zinc-900/35 px-4 py-3 shadow-inner shadow-black/20">
      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end lg:gap-x-4 lg:gap-y-2">
        <div className="flex flex-col gap-1 min-w-[12rem] flex-1">
          <label htmlFor="alert-filter-type" className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Type d’attaque
          </label>
          <AttackTypeCombobox
            value={filter.attackType}
            attackTypes={attackTypes}
            onSelect={(attackType) => onChange({ ...filter, attackType })}
          />
        </div>

        <div className="flex flex-col gap-1 min-w-[11rem] flex-1">
          <label htmlFor="alert-filter-severity" className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Criticité
          </label>
          <select
            id="alert-filter-severity"
            value={filter.severity}
            onChange={(e) =>
              onChange({
                ...filter,
                severity: e.target.value as AlertsFilterState["severity"],
              })
            }
            className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-100 focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30"
          >
            {SEVERITY_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1 min-w-[10rem]">
          <label htmlFor="alert-filter-from" className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Du (début attaque)
          </label>
          <input
            id="alert-filter-from"
            type="date"
            value={filter.dateFrom}
            onChange={(e) => onChange({ ...filter, dateFrom: e.target.value })}
            className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-100 focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 [color-scheme:dark]"
          />
        </div>

        <div className="flex flex-col gap-1 min-w-[10rem]">
          <label htmlFor="alert-filter-to" className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Au (fin attaque)
          </label>
          <input
            id="alert-filter-to"
            type="date"
            value={filter.dateTo}
            onChange={(e) => onChange({ ...filter, dateTo: e.target.value })}
            className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-100 focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 [color-scheme:dark]"
          />
        </div>

        <div className="flex items-center pb-0.5 lg:ml-auto">
          <button
            type="button"
            disabled={!active}
            onClick={() => onChange(defaultAlertsFilterState())}
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-white/[0.07] hover:text-white disabled:pointer-events-none disabled:opacity-35"
          >
            <FilterX size={14} strokeWidth={2} aria-hidden />
            Réinitialiser
          </button>
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">
        Les dates filtrent par chevauchement avec la fenêtre d’attaque (début → fin). Fuseau horaire local pour les bornes « du / au ».
      </p>
    </div>
  );
}
