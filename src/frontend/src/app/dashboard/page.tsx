import AlertsHomeClient from "@/components/dashboard/AlertsHomeClient";
import { getFakePredictions } from "@/lib/fakePredictions";

export const metadata = {
  title: "Alertes — CLAIR OBSCUR",
};

export default function DashboardHomePage() {
  const { alerts } = getFakePredictions();

  return (
    <div className="flex w-full flex-col gap-8">
      <AlertsHomeClient alerts={alerts} />
    </div>
  );
}
