"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, RefreshCw, Server, Trash2, X } from "lucide-react";
import { approveVm, fetchVms, rejectVm, revokeVm } from "@/lib/api";
import type { VmRecord, VmStatus } from "@/types/vms";

const STATUS_LABEL: Record<VmStatus, string> = {
  pending: "En attente",
  approved: "Connectée",
  rejected: "Refusée",
  revoked: "Révoquée",
};

const STATUS_STYLE: Record<VmStatus, string> = {
  pending: "bg-amber-500/15 text-amber-200 ring-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-200 ring-emerald-500/30",
  rejected: "bg-red-500/15 text-red-200 ring-red-500/30",
  revoked: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30",
};

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function VmsAdminClient() {
  const [vms, setVms] = useState<VmRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVms();
      setVms(data.vms);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const runAction = async (vmId: string, action: "approve" | "reject" | "revoke") => {
    setActing(vmId);
    setError(null);
    try {
      if (action === "approve") await approveVm(vmId);
      else if (action === "reject") await rejectVm(vmId);
      else await revokeVm(vmId);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setActing(null);
    }
  };

  const pending = vms.filter((v) => v.status === "pending");
  const connected = vms.filter((v) => v.status === "approved");

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-blue-400">
            <Server size={22} aria-hidden />
            <span className="text-xs font-semibold uppercase tracking-[0.18em]">Capteurs</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">VMs connectées</h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            Approuvez ou refusez les machines qui demandent à envoyer des logs. Chaque VM approuvée reçoit un
            préfixe S3 dédié dans le bucket raw-logs.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void reload()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-zinc-900/80 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:border-blue-500/40 hover:text-white disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden />
          Actualiser
        </button>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total" value={vms.length} />
        <StatCard label="En attente" value={pending.length} accent="amber" />
        <StatCard label="Connectées" value={connected.length} accent="emerald" />
      </div>

      {error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}

      {pending.length > 0 ? (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-amber-400/90">
            Demandes en attente ({pending.length})
          </h2>
          <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-950/60">
            <VmTable vms={pending} acting={acting} onAction={runAction} highlightPending />
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">Toutes les VMs</h2>
        {loading && vms.length === 0 ? (
          <p className="text-sm text-zinc-500">Chargement…</p>
        ) : vms.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-zinc-950/40 px-6 py-12 text-center">
            <Server className="mx-auto mb-3 text-zinc-600" size={36} aria-hidden />
            <p className="text-sm text-zinc-400">Aucune VM enregistrée.</p>
            <p className="mt-2 text-xs text-zinc-500">
              Sur une machine distante :{" "}
              <code className="rounded bg-zinc-900 px-1.5 py-0.5">sudo ./connect.sh --api-url http://…:8020</code>
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-950/60">
            <VmTable vms={vms} acting={acting} onAction={runAction} />
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: "amber" | "emerald" }) {
  const ring =
    accent === "amber" ? "ring-amber-500/20" : accent === "emerald" ? "ring-emerald-500/20" : "ring-white/10";
  return (
    <div className={`rounded-2xl border border-white/[0.08] bg-zinc-950/50 px-5 py-4 ring-1 ${ring}`}>
      <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums text-white">{value}</p>
    </div>
  );
}

function VmTable({
  vms,
  acting,
  onAction,
  highlightPending,
}: {
  vms: VmRecord[];
  acting: string | null;
  onAction: (vmId: string, action: "approve" | "reject" | "revoke") => void;
  highlightPending?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-white/[0.06] text-xs uppercase tracking-wider text-zinc-500">
            <th className="px-4 py-3 font-medium">Hostname</th>
            <th className="px-4 py-3 font-medium">Statut</th>
            <th className="px-4 py-3 font-medium">Enregistrée</th>
            <th className="px-4 py-3 font-medium">Dernier envoi</th>
            <th className="px-4 py-3 font-medium">Préfixe S3</th>
            <th className="px-4 py-3 font-medium text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {vms.map((vm) => (
            <tr
              key={vm.vm_id}
              className={`border-b border-white/[0.04] transition hover:bg-white/[0.02] ${
                highlightPending ? "bg-amber-500/[0.03]" : ""
              }`}
            >
              <td className="px-4 py-3">
                <div className="font-medium text-zinc-100">{vm.hostname}</div>
                <div className="mt-0.5 font-mono text-[11px] text-zinc-500">{vm.vm_id.slice(0, 8)}…</div>
              </td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${STATUS_STYLE[vm.status]}`}
                >
                  {STATUS_LABEL[vm.status]}
                </span>
              </td>
              <td className="px-4 py-3 text-zinc-400">{fmtDate(vm.registered_at)}</td>
              <td className="px-4 py-3 text-zinc-400">{fmtDate(vm.last_ship_at)}</td>
              <td className="max-w-[200px] truncate px-4 py-3 font-mono text-[11px] text-zinc-500" title={vm.s3_prefix ?? ""}>
                {vm.s3_prefix ?? "—"}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-2">
                  {vm.status === "pending" ? (
                    <>
                      <ActionBtn
                        label="Approuver"
                        icon={<Check size={14} />}
                        variant="approve"
                        disabled={acting === vm.vm_id}
                        onClick={() => void onAction(vm.vm_id, "approve")}
                      />
                      <ActionBtn
                        label="Refuser"
                        icon={<X size={14} />}
                        variant="reject"
                        disabled={acting === vm.vm_id}
                        onClick={() => void onAction(vm.vm_id, "reject")}
                      />
                    </>
                  ) : null}
                  {vm.status === "approved" ? (
                    <ActionBtn
                      label="Révoquer"
                      icon={<Trash2 size={14} />}
                      variant="reject"
                      disabled={acting === vm.vm_id}
                      onClick={() => void onAction(vm.vm_id, "revoke")}
                    />
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionBtn({
  label,
  icon,
  variant,
  disabled,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  variant: "approve" | "reject";
  disabled?: boolean;
  onClick: () => void;
}) {
  const cls =
    variant === "approve"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20"
      : "border-red-500/30 bg-red-500/10 text-red-200 hover:bg-red-500/20";
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition disabled:opacity-40 ${cls}`}
    >
      {icon}
      {label}
    </button>
  );
}
