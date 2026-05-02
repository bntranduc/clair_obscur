import { LogsExplorer } from "@/components/dashboard/LogsExplorer";

/** Onglet dédié : tableau plein champs + premier fichier auto-chargé. */
export default function NormalizedEventsPage() {
  return <LogsExplorer title="Événements normalisés" autoSelectFirst />;
}
