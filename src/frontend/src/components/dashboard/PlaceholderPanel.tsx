import { Layers } from "lucide-react";

export default function PlaceholderPanel({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center justify-center px-4 py-16 text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/15 to-red-500/15 ring-1 ring-white/10">
        <Layers className="h-8 w-8 text-blue-400/80" strokeWidth={1.5} />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1>
      {description && <p className="mt-3 text-[15px] leading-relaxed text-zinc-400">{description}</p>}
      <div className="mt-10 w-full max-w-md rounded-xl border border-dashed border-zinc-700/80 bg-zinc-900/40 px-6 py-8">
        <p className="text-sm text-zinc-500">Cette section sera branchée sur les données et workflows à venir.</p>
      </div>
    </div>
  );
}
