import AlertsPageClient from "@/components/dashboard/AlertsPageClient";

export const metadata = {
  title: "Alertes — CLAIR OBSCUR",
};

export default function AlertesPage() {
  return (
    <div className="flex w-full flex-col gap-8">
      <AlertsPageClient />
    </div>
  );
}
