import type { Metadata } from "next";
import AlertClusterGraphPanel from "@/components/dashboard/AlertClusterGraphPanel";

export const metadata: Metadata = {
  title: "Clusters d’alertes — CLAIR OBSCUR",
};

export default function ClustersPage() {
  return (
    <div className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden">
      <AlertClusterGraphPanel />
    </div>
  );
}
