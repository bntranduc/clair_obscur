"use client";

import {
  NORMALIZED_TABLE_COLUMNS,
  formatScalarCell,
  getNormalizedCell,
} from "@/lib/normalizedTable";

type Props = {
  logs: Record<string, unknown>[];
  truncated: boolean;
  offsetLines: number;
  limitLines: number;
};

export function NormalizedEventsTable({ logs, truncated, offsetLines, limitLines }: Props) {
  return (
    <>
      <p className="px-4 py-2 text-xs text-zinc-500">
        {logs.length} ligne(s)
        {truncated ? " (tronqué)" : ""} — offset {offsetLines}, limite {limitLines}
      </p>
      <div className="overflow-x-auto overflow-y-auto max-h-[min(70vh,560px)] border-t border-white/5">
        <table className="text-[11px] border-collapse align-top min-w-max">
          <thead className="sticky top-0 z-10 bg-zinc-950 shadow-[0_1px_0_0_rgba(255,255,255,0.06)]">
            <tr>
              {NORMALIZED_TABLE_COLUMNS.map((col) => (
                <th
                  key={col}
                  className="text-left font-semibold text-zinc-400 px-2 py-2 border-b border-white/10 whitespace-nowrap bg-zinc-950 min-w-[6rem]"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((row, i) => (
              <tr key={i} className="border-b border-white/[0.06] hover:bg-white/[0.03]">
                {NORMALIZED_TABLE_COLUMNS.map((col) => {
                  const v = getNormalizedCell(row, col);
                  const text = formatScalarCell(v);
                  const wide = col === "uri" || col === "user_agent" || col === "message" || col === "s3_key";
                  return (
                    <td
                      key={col}
                      className={`px-2 py-1.5 text-zinc-300 align-top border-r border-white/[0.04] last:border-r-0 min-w-[6rem] ${wide ? "max-w-[min(24rem,40vw)]" : "max-w-[12rem]"}`}
                      title={text === "—" ? "" : text}
                    >
                      <span className="block max-h-28 overflow-y-auto whitespace-pre-wrap break-words">
                        {text}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
