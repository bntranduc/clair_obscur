"use client";

import { useState } from "react";
import AlertTicketCard from "@/components/dashboard/AlertTicketCard";
import AlertsListToolbar, { type AlertsLayoutMode } from "@/components/dashboard/AlertsListToolbar";
import type { ModelAlert } from "@/types/modelPrediction";

export default function AlertsHomeClient({ alerts }: { alerts: ModelAlert[] }) {
  const [layout, setLayout] = useState<AlertsLayoutMode>("grid");

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

      <div
        className={
          layout === "grid"
            ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
            : "flex flex-col gap-2"
        }
      >
        {alerts.map((alert) => (
          <AlertTicketCard key={alert.challenge_id} alert={alert} layout={layout} />
        ))}
      </div>
    </>
  );
}
