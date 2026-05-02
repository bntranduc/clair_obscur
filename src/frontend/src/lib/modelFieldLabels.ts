/**
 * Libellés FR pour les champs bruts renvoyés par le modèle (clés JSON).
 * Clés inconnues : fallback lisible (snake_case → mots).
 */
const LABELS: Record<string, string> = {
  // Identifiants & méta
  challenge_id: "Scénario / corrélation",
  attack_type: "Type d’attaque",
  attacker_ips: "Adresses IP sources",
  victim_accounts: "Comptes ou identités ciblés",
  attack_start_time: "Début de la fenêtre d’attaque",
  attack_end_time: "Fin de la fenêtre d’attaque",
  indicators: "Indicateurs et signaux",
  detection_time_seconds: "Fenêtre d’agrégation (secondes)",
  // confidence / scores
  severity: "Niveau de criticité (score)",
  alert_summary: "Résumé opérationnel (score)",
  remediation_proposal: "Proposition de remédiation (score)",
  detection: "Sous-scores par champ de détection",
  reasons: "Justifications textuelles",
  // indicators keys (exemples)
  failures: "Nombre d’échecs",
  distinct_users: "Comptes distincts touchés",
  union_select: "Présence UNION SELECT",
  paths_seen: "Chemins suspects observés",
  callback_hosts: "Hôtes de callback (SSRF)",
  bytes_estimate: "Volume transféré (estimation)",
  dest_regions: "Zones de destination",
  rule_ids: "Règles déclenchées",
  failure_count: "Total échecs",
  distinct_usernames: "Identifiants distincts",
};

function titleCaseWords(s: string): string {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Libellé français pour une clé de champ JSON. */
export function fieldLabelFr(key: string): string {
  return LABELS[key] ?? titleCaseWords(key);
}

/** Préfixe de chemin pour savoir si on formate les scores en %. */
export function pathIsConfidenceBranch(path: string): boolean {
  return path === "confidence" || path.startsWith("confidence.");
}
