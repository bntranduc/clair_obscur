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
          Plateforme NDR — logs et prédictions.
        </p>
        <Link
          href="/dashboard/logs"
          className="px-8 py-4 bg-white text-black font-semibold rounded-full hover:bg-gray-200 transition-all"
        >
          Logs S3
        </Link>
      </main>

      <footer className="absolute bottom-8 text-gray-500 text-sm z-10">
        &copy; {new Date().getFullYear()} CLAIR OBSCUR
      </footer>
    </div>
  );
}
