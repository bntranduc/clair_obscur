"use client";

import { useMemo, useState } from "react";
import AlertTicketCard from "@/components/dashboard/AlertTicketCard";
import AlertsFiltersBar from "@/components/dashboard/AlertsFiltersBar";
import AlertsListToolbar, { type AlertsLayoutMode } from "@/components/dashboard/AlertsListToolbar";
import {
  defaultAlertsFilterState,
  filterAlerts,
  uniqueAttackTypes,
  type AlertsFilterState,
} from "@/lib/filterAlerts";
import type { ModelAlert } from "@/types/modelPrediction";

export default function AlertsHomeClient({ alerts }: { alerts: ModelAlert[] }) {
  const [layout, setLayout] = useState<AlertsLayoutMode>("grid");
  const [filter, setFilter] = useState<AlertsFilterState>(() => defaultAlertsFilterState());

  const attackTypes = useMemo(() => uniqueAttackTypes(alerts), [alerts]);
  const filtered = useMemo(() => filterAlerts(alerts, filter), [alerts, filter]);

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Alertes</h1>
          <p className="max-w-3xl text-[15px] leading-relaxed text-zinc-400">
            Prédictions du modèle (jeu de démonstration). Aperçu rapide via le bouton à côté du type, ou ouverture de la
            fiche complète. Chaque étiquette indique la date de début de l’attaque.
          </p>
        </header>
        <AlertsListToolbar mode={layout} onModeChange={setLayout} />
      </div>

      <AlertsFiltersBar filter={filter} attackTypes={attackTypes} onChange={setFilter} />

      <p className="text-sm text-zinc-500">
        <span className="tabular-nums text-zinc-400">{filtered.length}</span> alerte
        {filtered.length === 1 ? "" : "s"}
        {filtered.length !== alerts.length ? (
          <>
            {" "}
            sur <span className="tabular-nums text-zinc-400">{alerts.length}</span>
          </>
        ) : null}
      </p>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/15 bg-zinc-900/25 px-6 py-12 text-center text-sm text-zinc-500">
          Aucune alerte ne correspond aux filtres. Essayez d’élargir le type, la criticité ou la plage de dates.
        </div>
      ) : (
        <div
          className={
            layout === "grid"
              ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
              : "flex flex-col gap-2"
          }
        >
          {filtered.map((alert) => (
            <AlertTicketCard key={alert.challenge_id} alert={alert} layout={layout} />
          ))}
        </div>
      )}
    </>
  );
}
