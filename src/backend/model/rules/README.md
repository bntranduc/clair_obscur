# Rules Engine — Detection Signals

`rules_window.py` implements deterministic detection rules over a batch of normalized log events.
It returns a list of `Signal` objects fed into `aggregate_signals.py`, then sent to the LLM.

---

## Pipeline position

```
raw logs → normalize → detect_signals_window_1h() → aggregate_signals() → LLM → alerts
```

---

## Rule catalog

### Authentication

| Rule ID | Trigger | Source |
|---|---|---|
| `CREDENTIAL_STUFFING` | ≥100 auth failures, ≥10 distinct users, ≥90% failure rate | `authentication` |
| `CREDENTIAL_STUFFING_USER_TARGETED` | ≥50 failures toward same username from a stuffing IP | `authentication` |
| `CREDENTIAL_STUFFING_SUCCESS` | Auth success from a stuffing IP | `authentication` |
| `SSH_BRUTEFORCE` | ≥200 SSH failures from external IP, or burst of ≥5 in 10s | `authentication` |
| `SSH_BRUTEFORCE_SSH_ONLY` | ≥200 failures, 100% SSH method | `authentication` |
| `SUSPICIOUS_GEO` | Traffic from RU/CN/KP with no FR baseline | all |

### SSH post-exploitation (system logs)

| Rule ID | Trigger | Source |
|---|---|---|
| `SSH_PRIV_ESC` | Privileged command (`sudo -i`, `adduser`, `chmod +s`…) from SSH-targeted user | `system` |
| `SSH_LATERAL_MOVE` | SSH login accepted from internal IP, in context of SSH bruteforce | `system` |
| `SSH_EXFIL` | >5 MB sent from internal host to SSH bruteforce IP | `network` |

### Web application

| Rule ID | Trigger | Source |
|---|---|---|
| `SSRF` | ≥3 SSRF payloads (internal URL / dangerous scheme) from same IP | `application` |
| `DIRECTORY_TRAVERSAL` | ≥5 path traversal patterns (`../`, encoded variants) from same IP | `application` |
| `DIRECTORY_TRAVERSAL_SUCCESS` | ≥1 traversal returning 200 + sensitive path | `application` |
| `SQL_INJECTION` | ≥3 SQLi patterns (UNION, `'OR`, `sqlmap`…) from same IP | `application` |
| `WEB_SQLI_AUTOMATED` | ≥20 SQLi hits in 300s (burst detection) | `application` |
| `SQL_INJECTION_MANY_500` | ≥50 HTTP 500 with SQLi in URI from same IP | `application` |
| `SQL_INJECTION_EXFIL` | SQLi IP + >5 MB network exfil from internal hosts | `application` + `network` |
| `SQL_INJECTION_SQLMAP_UA` | `sqlmap` string in User-Agent | `application` |
| `WEB_WEBSHELL` | Known webshell filename or `?cmd=` pattern in URI | `application` |
| `WEB_LFI_RFI` | ≥3 PHP wrapper / dangerous scheme / absolute sensitive path hits from same IP (`php://`, `file://`, `expect://`, `/etc/passwd`, RFI…) | `application` |
| `WEB_SENSITIVE_FILE_ACCESS` | 1 hit on high-value file path (`.git/config`, `.env`, `.aws/credentials`, `backup.sql`, `actuator/heapdump`…) — severity escalates to critical if status 200 | `application` |
| `WEB_LOG4SHELL` | `${jndi:…}` or obfuscation variant in URI / User-Agent / Referer (1 hit sufficient) | `application` |
| `WEB_NIKTO_SCAN` | `Nikto` in User-Agent (1 hit sufficient) | `application` |
| `WEB_SCANNER_UA_DETECTED` | Known vuln-scanner UA: Nessus, OpenVAS, Qualys, Acunetix, Burp Suite (1 hit sufficient) | `application` |
| `WEB_DIR_BRUTEFORCE` | ≥50 HTTP 404 in 300s from same IP (burst detection) | `application` |
| `WEB_BRUTEFORCE_HTTP` | ≥20 POST 401/403 on login endpoint in 900s | `application` |
| `WEB_BRUTEFORCE_HTTP_UA` | `Hydra` in User-Agent (1 hit sufficient) | `application` |
| `WEB_BRUTEFORCE_HTTP_SUCCESS` | POST 200 on login endpoint from a bruteforce IP | `application` |
| `WEB_IDOR` | ≥10 GET 200 on API endpoints + (sequential IDs **or** ≥5 distinct IDs) from same IP | `application` |

### Network

| Rule ID | Trigger | Source |
|---|---|---|
| `NET_REVERSE_SHELL` | Internal host connects to known reverse-shell port (4444, 1337…) | `network` |
| `NET_PORT_SCAN` | ≥15 distinct destination ports from same src→dst pair | `network` |
| `NET_PORT_SCAN_BURST` | ≥10 distinct ports in 10s from same src→dst pair | `network` |
| `NET_NMAP_USERAGENT` | `nmap` in User-Agent (1 hit sufficient) | `application` |

### System — post-exploitation

| Rule ID | Trigger | Source |
|---|---|---|
| `SYS_CREDENTIAL_DUMP` | `cat /etc/shadow`, `mimikatz`, `ntds.dit`, `lsass`, `.aws/credentials`… (1 hit sufficient) | `system` |
| `SYS_LOG_TAMPERING` | `history -c`, `rm /var/log`, `truncate -s 0`, `unset HISTFILE`… | `system` |
| `SYS_PERSISTENCE` | `crontab -e`, `systemctl enable`, `>> /etc/rc.local`… | `system` |
| `SYS_BACKDOOR_ACCOUNT` | `useradd`, `usermod -aG sudo`, `>> /etc/sudoers`… | `system` |
| `SYS_EXFIL_TOOL` | `curl -T`, `wget --post-file`, `curl ./etc/`… | `system` |

### Kill chain correlations

| Rule ID | Trigger |
|---|---|
| `KILL_CHAIN_RECON_TO_EXPLOIT` | Port scan IP → exploitation rule (same window) |
| `KILL_CHAIN_WEBSCAN_TO_EXPLOIT` | Nikto / dir-bruteforce / vuln-scanner IP → exploitation rule (same window) |
| `KILL_CHAIN_WEBBRUTEFORCE_TO_EXPLOIT` | HTTP bruteforce IP → exploitation rule (same window) |
| `KILL_CHAIN_COMPROMISE_AND_COVER` | Log tampering on already-compromised host |
| `KILL_CHAIN_PERSISTENCE` | Persistence/backdoor on already-compromised host |
| `KILL_CHAIN_SHELL_TO_EXFIL` | curl/wget exfil on already-compromised host |
| `KILL_CHAIN_LFI_TO_WEBSHELL` | `WEB_LFI_RFI` + `WEB_WEBSHELL` from same IP → `attack_type=lfi_to_rce` (T1190→T1505.003) |
| `KILL_CHAIN_LOG4SHELL_TO_SHELL` | `WEB_LOG4SHELL` attacker IP == `NET_REVERSE_SHELL` C2 destination → `attack_type=log4shell_rce` (T1190/CVE-2021-44228→T1059→T1071) |
| `KILL_CHAIN_CRED_DUMP_TO_EXFIL` | `SYS_CREDENTIAL_DUMP` on host H + `SYS_EXFIL_TOOL` (same host) or `SSH_EXFIL` (window-level) → `attack_type=credential_exfiltration` (T1003→T1041) |

---

## Thresholds (all tunable via function parameters)

| Parameter | Default | Rule |
|---|---|---|
| `cs_failures_threshold` | 100 | CREDENTIAL_STUFFING |
| `cs_distinct_users_threshold` | 10 | CREDENTIAL_STUFFING |
| `cs_failure_ratio_threshold` | 0.90 | CREDENTIAL_STUFFING |
| `cs_user_failures_threshold` | 50 | CREDENTIAL_STUFFING_USER_TARGETED |
| `ssh_failures_threshold` | 200 | SSH_BRUTEFORCE |
| `ssh_burst_n` / `ssh_burst_seconds` | 5 / 10s | SSH_BRUTEFORCE (burst) |
| `ssrf_min_hits` | 3 | SSRF |
| `traversal_min_hits` | 5 | DIRECTORY_TRAVERSAL |
| `sqli_min_hits` | 3 | SQL_INJECTION |
| `sqli_volume_min` / `sqli_volume_window_sec` | 20 / 300s | WEB_SQLI_AUTOMATED |
| `port_scan_threshold` | 15 ports | NET_PORT_SCAN |
| `burst_min_ports` / `burst_window_seconds` | 10 / 10s | NET_PORT_SCAN_BURST |
| `dir_bruteforce_threshold` / `dir_bruteforce_window_sec` | 50 / 300s | WEB_DIR_BRUTEFORCE |
| `http_bruteforce_threshold` / `http_bruteforce_window_sec` | 20 / 900s | WEB_BRUTEFORCE_HTTP |
| `idor_threshold` | 10 | WEB_IDOR |
| `idor_distinct_ids_threshold` | 5 | WEB_IDOR (min distinct numeric IDs to qualify as enumeration) |
| `lfi_rfi_min_hits` | 3 | WEB_LFI_RFI |
| _(no threshold)_ | 1 | WEB_SENSITIVE_FILE_ACCESS |
| `cred_dump_threshold` | 1 | SYS_CREDENTIAL_DUMP |
| `log4shell_threshold` | 1 | WEB_LOG4SHELL |
| `log_tamper_threshold` | 1 | SYS_LOG_TAMPERING |
| `persistence_threshold` | 1 | SYS_PERSISTENCE |
| `backdoor_account_threshold` | 1 | SYS_BACKDOOR_ACCOUNT |
| `exfil_tool_threshold` | 1 | SYS_EXFIL_TOOL |

---

## False positive notes

- **`WEB_DIR_BRUTEFORCE`** and **`WEB_BRUTEFORCE_HTTP`** use sliding-window burst detection — total 404/401 count over a week does not trigger them.
- **`SSH_BRUTEFORCE`** excludes internal IPs (`10/8`, `172.16/12`, `192.168/16`). Lateral movement from internal IPs is handled by `SSH_LATERAL_MOVE`.
- **`SYS_*` rules** match message patterns in `log_source: system`. All use `break` after first match per event to avoid double-counting.
- **`WEB_IDOR`** requires sequential IDs **or** ≥5 distinct IDs in addition to the hit threshold. A normal user repeatedly accessing the same resource (`/api/users/42` × 15) will not trigger — only enumeration patterns will (sequential: `42, 43, 44…`, or scatter: `3, 17, 89, 201…`).
- **`WEB_SCANNER_UA_DETECTED`** fires on the first hit — no threshold needed. Zero expected false positives: no legitimate browser or service embeds "Nessus", "Burp", etc. in its User-Agent. Regex source: ModSecurity CRS `REQUEST-913-SCANNER-DETECTION`.

---

## Adding a new rule (checklist)

1. Add regex constant at module level (before `detect_signals_window_1h`)
2. Add threshold parameter to function signature
3. Add accumulator dict in the data-structure section
4. Add detection logic in the `for e in events:` loop
5. Add signal emission after the loop (follow the existing `# --- Emit X ---` pattern)
6. Test: `0 new-rule signals on week1 + week2` before enabling

## References

- MITRE ATT&CK: https://attack.mitre.org/
- OWASP Testing Guide v4.2: https://owasp.org/www-project-web-security-testing-guide/
- SANS FOR508 — Linux Forensics
