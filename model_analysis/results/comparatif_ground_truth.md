# Comparatif Pipeline vs Ground Truth — Dataset 1

## SSH Brute Force (100 pts)

| Champ | Ground Truth | Pipeline | Statut |
|---|---|---|---|
| attack_type | `ssh_brute_force` | `ssh_brute_force` (1 seule alerte) | ✅ |
| attacker_ips | 45.33.32.156, 198.51.100.89 | 198.51.100.89, 45.33.32.156 | ✅ |
| victim_accounts | sysadmin | sysadmin | ✅ |
| window start | 01:00:00 | 01:00:00 | ✅ |
| window end | **07:00:00** | **06:16:30** | ⚠️ -44 min |
| failed_ssh | ~4 600 | 4 650 | ✅ |
| priv_esc | sudo + backdoor user | détecté (commandes complètes) | ✅ |
| lateral_targets | app-prod-01, app-prod-02, **db-prod-01**, web-prod-01 | app-prod-01, app-prod-02, web-prod-01, **web-prod-02** | ⚠️ db-prod-01 manquant, web-prod-02 en trop |
| exfil | dans ssh_brute_force | dans ssh_brute_force | ✅ |

## Credential Stuffing (100 pts)

| Champ | Ground Truth | Pipeline | Statut |
|---|---|---|---|
| attack_type | `credential_stuffing` | `credential_stuffing` | ✅ |
| attacker_ips | 203.0.113.45, 198.51.100.23 | 198.51.100.23, 203.0.113.45 | ✅ |
| victim_accounts | jdupont | jdupont | ✅ |
| window start | 02:00:00 | 02:00:05 | ✅ |
| window end | **06:00:00** | **05:42:21** | ⚠️ -18 min |
| failed_logins | ~3 500 | 3 594 | ✅ |
| web_shell | /uploads/image_2026.php | détecté | ✅ |
| reverse_shell_port | 4444 | 4444 | ✅ |
| geolocation | Beijing (CN) | CN | ✅ |

## SQL Injection (100 pts)

| Champ | Ground Truth | Pipeline | Statut |
|---|---|---|---|
| attack_type | `sql_injection` | `sql_injection` | ✅ |
| attacker_ips | 185.220.101.45 | 185.220.101.45 | ✅ |
| victim_accounts | — | — | ✅ |
| window start | 14:00:00 | 14:00:00 | ✅ |
| window end | **17:00:00** | **16:43:10** | ⚠️ -17 min |
| sqli_payloads | ~300 | 342 | ✅ |
| exfil_bytes | **~25 MB** | **~50 MB** | ❌ x2 surestimé |
| tool_signature | Chrome-like + automated | WEB_SQLI_AUTOMATED (pas de UA) | ⚠️ partiel |

## Directory Traversal (80 pts)

| Champ | Ground Truth | Pipeline | Statut |
|---|---|---|---|
| attack_type | `directory_traversal` | `directory_traversal` | ✅ |
| attacker_ips | 198.51.100.200 | 198.51.100.200 | ✅ |
| victim_accounts | — | — | ✅ |
| window start | 10:00:00 | 10:00:00 | ✅ |
| window end | **12:00:00** | **11:23:00** | ⚠️ -37 min |
| successful_reads | ~75 | 77 | ✅ |
| sensitive_files | /etc/passwd, /etc/shadow, /root/.ssh/id_rsa | idem + /etc/hosts | ✅ |

## SSRF (80 pts)

| Champ | Ground Truth | Pipeline | Statut |
|---|---|---|---|
| attack_type | `ssrf` | `ssrf` | ✅ |
| attacker_ips | 203.0.113.100 | 203.0.113.100 | ✅ |
| victim_accounts | — | — | ✅ |
| window start | 11:00:00 | 11:00:00 | ✅ |
| window end | **12:00:00** | **12:13:30** | ⚠️ +13 min |
| ssrf_targets (GT) | 10.0.3.10:3306, 10.0.4.10:389, 169.254.169.254 | tous présents + 10.0.2.10:8080, 10.0.3.10:5432 | ✅ (superset) |
| internal_traffic_from_web | true | non extrait explicitement | ⚠️ |

## Synthèse globale

| Attaque | Type | IPs | Comptes | Fenêtre | Indicateurs clés | Points max |
|---|---|---|---|---|---|---|
| SSH Brute Force | ✅ | ✅ | ✅ | ⚠️ fin -44min | ✅ sauf db-prod-01 manquant | 100 |
| Credential Stuffing | ✅ | ✅ | ✅ | ⚠️ fin -18min | ✅ | 100 |
| SQL Injection | ✅ | ✅ | ✅ | ⚠️ fin -17min | ❌ exfil x2 surestimé | 100 |
| Directory Traversal | ✅ | ✅ | ✅ | ⚠️ fin -37min | ✅ | 80 |
| SSRF | ✅ | ✅ | ✅ | ⚠️ fin +13min | ✅ | 80 |

### Points à corriger

- **Fenêtres de fin** : systématiquement décalées (l'agrégation coupe à la dernière fenêtre glissante de 15 min plutôt qu'au dernier événement réel).
- **SQL Injection — exfil** : surestimée à ~50 MB vs ~25 MB dans le ground truth.
- **SSH — lateral targets** : `db-prod-01` non détecté, `web-prod-02` détecté à tort.
