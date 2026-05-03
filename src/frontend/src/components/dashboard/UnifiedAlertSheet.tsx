import type { UnifiedRow } from "@/lib/buildUnifiedAlertRows";
import { scoreToneClass } from "@/lib/buildUnifiedAlertRows";

function ScorePill({ p }: { p: number }) {
  const pct = Math.round(p * 1000) / 10;
  return (
    <span
      className={`inline-flex min-w-[3.25rem] justify-end tabular-nums text-[13px] font-semibold ${scoreToneClass(p)}`}
    >
      {pct}%
    </span>
  );
}

export default function UnifiedAlertSheet({ rows }: { rows: UnifiedRow[] }) {
  return (
    <div>
      {rows.map((row) => (
        <div
          key={row.id}
          className="border-b border-white/[0.06] py-2.5 last:border-b-0 last:pb-0"
        >
          {row.label ? (
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">{row.label}</p>
          ) : null}
          <div className="flex items-start justify-between gap-3">
            <p
              className={`min-w-0 flex-1 text-[13px] leading-snug text-zinc-100 ${row.isContinuation ? "border-l border-blue-500/20 pl-2" : ""}`}
            >
              {row.isContinuation ? <span className="text-zinc-600">↳ </span> : null}
              {row.value}
            </p>
            {row.score !== undefined ? (
              <div className="shrink-0 pt-0.5">
                <ScorePill p={row.score} />
              </div>
            ) : null}
          </div>
          {row.reason ? (
            <p className="mt-1 text-[12px] leading-relaxed text-zinc-500">{row.reason}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
