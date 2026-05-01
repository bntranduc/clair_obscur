import { PredictionsAlertsPage } from "@/components/dashboard/PredictionsAlertsPage";

export default function AlertsPage() {
  return (
    <PredictionsAlertsPage
      apiPrefix="/api/v1/alerts"
      title="Alertes"
      bucketLabel="model-attacks-predictions"
    />
  );
}
