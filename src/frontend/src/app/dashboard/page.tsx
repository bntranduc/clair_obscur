import Link from "next/link";

export default function DashboardHome() {
  return (
    <div className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Accueil dashboard</h1>
      <p className="text-gray-400 max-w-xl">
        Consultez les fichiers de logs stockés dans S3 (préfixe OpenSearch) et affichez un échantillon de
        lignes normalisées via l&apos;API dashboard.
      </p>
      <div className="flex flex-col gap-2 text-indigo-400">
        <Link href="/dashboard/logs" className="hover:text-indigo-300 underline w-fit">
          → Logs S3
        </Link>
        <Link href="/dashboard/alerts" className="hover:text-indigo-300 underline w-fit">
          → Alertes (prédictions prod)
        </Link>
        <Link href="/dashboard/alerts-tmp" className="hover:text-indigo-300 underline w-fit">
          → Alertes (TMP)
        </Link>
      </div>
    </div>
  );
}
