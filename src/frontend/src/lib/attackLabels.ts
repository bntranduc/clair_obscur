const LABELS: Record<string, string> = {
  ssh_brute_force: "Force brute SSH",
  credential_stuffing: "Credential stuffing",
  sql_injection: "Injection SQL",
  directory_traversal: "Directory traversal",
  ssrf: "SSRF",
  exfiltration: "Exfiltration",
};

/** Libellé lisible pour un identifiant de type d’attaque (challenge_id / attack_type). */
export function attackDisplayName(id: string): string {
  if (LABELS[id]) return LABELS[id];
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
