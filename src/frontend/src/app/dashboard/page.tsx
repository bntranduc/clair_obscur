import Link from "next/link";

export default function DashboardHomePage() {
  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
      <p className="text-zinc-400">
        Consulte les fichiers de logs bruts indexés dans S3 (OpenSearch export), normalisés pour affichage.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link
          href="/dashboard/logs"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
        >
          Logs S3
        </Link>
        <Link
          href="/dashboard/events"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm font-medium transition-colors border border-white/10"
        >
          Événements (tableau)
        </Link>
        <Link
          href="/dashboard/test-model"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600/90 hover:bg-indigo-500 text-white text-sm font-medium transition-colors border border-indigo-400/30"
        >
          Tester modèle
        </Link>
        <Link
          href="/dashboard/chat"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600/85 hover:bg-violet-500 text-white text-sm font-medium transition-colors border border-violet-400/25"
        >
          Assistant Clair Obscur
        </Link>
        <Link
          href="/dashboard/incidents"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-amber-500/25 to-orange-500/20 hover:from-amber-500/35 hover:to-orange-500/25 text-amber-50 text-sm font-medium transition-colors border border-amber-500/35"
        >
          Incidents
        </Link>
        <Link
          href="/dashboard/alerts"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/10 hover:bg-amber-500/15 text-amber-200/90 text-sm font-medium transition-colors border border-amber-500/20"
        >
          Fichiers JSON
        </Link>
      </div>
    </div>
  );
}
