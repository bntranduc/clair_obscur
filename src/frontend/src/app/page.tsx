import ShaderBackground from "@/components/ui/ShaderBackground";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-zinc-950 text-white">
      <ShaderBackground />

      {/* Ambient orbs */}
      <div
        className="pointer-events-none absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-blue-500/15 blur-[100px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -right-24 bottom-1/4 h-80 w-80 rounded-full bg-red-600/12 blur-[90px]"
        aria-hidden
      />

      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-2xl text-center">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-blue-400/90">
            Network Detection & Response
          </p>
          <h1 className="bg-gradient-to-b from-white via-white to-zinc-400 bg-clip-text text-5xl font-bold tracking-tight text-transparent sm:text-7xl md:text-8xl">
            CLAIR OBSCUR
          </h1>
          <p className="mx-auto mt-6 max-w-md text-[15px] leading-relaxed text-zinc-400">
            Console d’analyse des événements normalisés et pilotage des investigations.
          </p>

          <div className="mt-12 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/dashboard/logs"
              className="group focus-ring inline-flex items-center justify-center gap-2 rounded-full bg-white px-8 py-3.5 text-sm font-semibold text-zinc-950 shadow-lg shadow-blue-500/10 transition hover:bg-zinc-100 hover:shadow-blue-500/20"
            >
              Ouvrir le tableau de bord
              <ArrowRight
                size={18}
                className="transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </Link>
            <Link
              href="/dashboard"
              className="focus-ring text-sm font-medium text-zinc-400 underline-offset-4 transition hover:text-white hover:underline"
            >
              Vue anomalies
            </Link>
          </div>
        </div>
      </main>

      <footer className="relative z-10 border-t border-white/[0.06] py-5 text-center text-[13px] text-zinc-600">
        © {new Date().getFullYear()} CLAIR OBSCUR
      </footer>
    </div>
  );
}
