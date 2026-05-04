import { Suspense } from "react";
import SettingsTabs from "@/components/dashboard/SettingsTabs";

export const metadata = {
  title: "Paramètres — CLAIR OBSCUR",
};

function SettingsFallback() {
  return (
    <div className="w-full space-y-4 pb-8">
      <div className="h-8 w-48 max-w-full animate-pulse rounded-lg bg-zinc-800/80" />
      <div className="h-4 w-full max-w-md animate-pulse rounded bg-zinc-800/60" />
      <div className="h-12 w-full max-w-lg animate-pulse rounded-xl bg-zinc-800/50" />
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="w-full min-w-0">
      <Suspense fallback={<SettingsFallback />}>
        <SettingsTabs />
      </Suspense>
    </div>
  );
}
