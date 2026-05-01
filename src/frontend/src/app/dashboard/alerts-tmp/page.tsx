import { PredictionsAlertsPage } from "@/components/dashboard/PredictionsAlertsPage";

export default function AlertsTmpPage() {
  return (
    <PredictionsAlertsPage
      apiPrefix="/api/v1/alerts-tmp"
      title="Alertes (TMP)"
      bucketLabel="model-attacks-predictions-tmp"
    />
  );
}
