import Link from "next/link";

export default function DashboardHome() {
  return (
    <div className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Accueil dashboard</h1>
      <p className="text-gray-400 max-w-xl">
        Consultez les fichiers de logs stockés dans S3 (préfixe OpenSearch) et affichez un échantillon de
        lignes normalisées via l&apos;API dashboard.
      </p>
      <ul className="space-y-2 text-indigo-400">
        <li>
          <Link href="/dashboard/logs" className="hover:text-indigo-300 underline">
            → Logs S3
          </Link>
        </li>
        <li>
          <Link href="/dashboard/alerts" className="hover:text-indigo-300 underline">
            → Alertes (model-attacks-predictions)
          </Link>
        </li>
        <li>
          <Link href="/dashboard/alerts-tmp" className="hover:text-indigo-300 underline">
            → Alertes TMP (model-attacks-predictions-tmp)
          </Link>
        </li>
        <li>
          <Link href="/dashboard/call-model" className="hover:text-indigo-300 underline">
            → Appeler le modèle (JSON → prédictions)
          </Link>
        </li>
      </ul>
    </div>
  );
}
