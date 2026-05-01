import Link from "next/link";
import ShaderBackground from "@/components/ui/ShaderBackground";

export default function Home() {
  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden text-white font-sans">
      <ShaderBackground />

      <main className="z-10 flex flex-col items-center text-center p-8 space-y-8 backdrop-blur-sm bg-black/30 rounded-3xl border border-white/10 shadow-2xl max-w-[95vw]">
        <h1 className="text-6xl md:text-8xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-b from-white to-gray-400">
          CLAIR OBSCUR
        </h1>
        <p className="text-xl md:text-2xl text-gray-300 max-w-2xl">
          Plateforme NDR — logs S3, prédictions et supervision.
        </p>

        <div className="flex gap-4 mt-4 flex-wrap justify-center">
          <Link
            href="/dashboard"
            className="px-8 py-4 bg-white text-black font-semibold rounded-full hover:bg-gray-200 transition-all transform hover:scale-105 shadow-lg border-2 border-transparent hover:border-gray-400"
          >
            Accéder au dashboard
          </Link>
          <Link
            href="/dashboard/logs"
            className="px-8 py-4 bg-transparent border border-white/30 text-white font-semibold rounded-full hover:bg-white/10 transition-all"
          >
            Logs S3
          </Link>
        </div>
      </main>

      <footer className="absolute bottom-8 text-gray-500 text-sm z-10">
        &copy; {new Date().getFullYear()} CLAIR OBSCUR
      </footer>
    </div>
  );
}
