"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import AlertsHomeClient from "@/components/dashboard/AlertsHomeClient";
import { fetchAllAlerts } from "@/lib/api";
import type { AlertCatalogItem } from "@/types/alertsCatalog";

export default function AlertsPageClient() {
  const [alerts, setAlerts] = useState<AlertCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchAllAlerts();
        if (!cancelled) setAlerts(data.alerts ?? []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-3 text-zinc-400">
        <Loader2 className="animate-spin" size={22} aria-hidden />
        Chargement du catalogue d’alertes…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-6 py-8 text-sm text-red-200">
        Impossible de charger les alertes : {error}
      </div>
    );
  }

  return <AlertsHomeClient alerts={alerts} />;
}
