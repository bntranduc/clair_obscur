"use client";

import { alertToCardModel } from "@/lib/alertPresentation";

export function PredictAlertsCards({ alerts }: { alerts: Record<string, unknown>[] }) {
  if (alerts.length === 0) return null;
  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
        {alerts.length} alerte(s)
      </p>
      {alerts.map((a, i) => {
        const card = alertToCardModel(a, i);
        return (
          <div
            key={`${card.id}-${i}`}
            className="rounded-xl border border-white/[0.07] bg-black/35 px-4 py-3 space-y-2"
          >
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-200 border border-emerald-500/25">
                {card.challengeId}
              </span>
              <span className="text-sm text-white capitalize">{card.attackType.replace(/_/g, " ")}</span>
            </div>
            <div className="grid gap-1 text-xs text-zinc-400">
              {card.windowLabel && (
                <div>
                  <span className="text-zinc-600">Fenêtre · </span>
                  {card.windowLabel}
                </div>
              )}
              {card.attackerIps.length > 0 && (
                <div className="font-mono">
                  <span className="text-zinc-600">IPs · </span>
                  {card.attackerIps.join(", ")}
                </div>
              )}
              {card.indicatorsPreview && (
                <div>
                  <span className="text-zinc-600">Indicateurs · </span>
                  {card.indicatorsPreview}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
