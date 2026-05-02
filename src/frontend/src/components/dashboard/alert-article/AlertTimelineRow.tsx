import { formatMaybeIsoDate } from "@/lib/alertDetailFormat";

export default function AlertTimelineRow({
  startIso,
  endIso,
  compact,
}: {
  startIso: string;
  endIso: string;
  compact?: boolean;
}) {
  const startFmt = formatMaybeIsoDate(startIso);
  const endFmt = formatMaybeIsoDate(endIso);
  const pad = compact
    ? "px-3 py-2 text-[10px]"
    : "px-5 py-4 sm:px-10 sm:py-5 lg:px-16 xl:px-24 2xl:px-28 text-[13px] sm:text-[14px]";

  return (
    <div
      className={`grid grid-cols-2 divide-x divide-white/[0.06] border-b border-white/[0.06] bg-black/15 ${pad}`}
    >
      <div className={compact ? "pr-2" : "pr-4 sm:pr-10"}>
        <p className="font-medium uppercase tracking-wide text-zinc-500">Début</p>
        <p className={`mt-1 font-medium leading-tight text-zinc-200 ${compact ? "line-clamp-2" : "sm:text-[15px]"}`}>
          {startFmt.primary}
        </p>
      </div>
      <div className={compact ? "pl-2" : "pl-4 sm:pl-10"}>
        <p className="font-medium uppercase tracking-wide text-zinc-500">Fin</p>
        <p className={`mt-1 font-medium leading-tight text-zinc-200 ${compact ? "line-clamp-2" : "sm:text-[15px]"}`}>
          {endFmt.primary}
        </p>
      </div>
    </div>
  );
}
