from __future__ import annotations

import ipaddress
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, TypedDict
from urllib.parse import unquote

from backend.log.normalization.types import NormalizedEvent


WINDOW_SECONDS = 900


class Signal(TypedDict, total=False):
    rule_id: str
    ts: str
    ts_end: str
    source_ip: str
    username: str
    hostname: str
    iocs: dict[str, Any]
    evidence_ids: list[str]


def _to_dt(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _safe_unquote(s: str) -> str:
    try:
        return unquote(unquote(s))
    except Exception:
        return s


REVERSE_SHELL_PORTS: frozenset[int] = frozenset({
    4444, 4445, 4446, 1337, 8888, 9001, 9999, 31337, 5555, 6666, 7777, 1234,
})

_INTERNAL_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


def _is_internal_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _INTERNAL_NETWORKS)
    except ValueError:
        return False


WEBSHELL_REGEXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/(c99|r57|wso|b374k|indoxploit|p0wny|alfa)\.php", re.I), "nom de webshell connu"),
    (re.compile(r"/(upload|uploads|files|images|img|media|tmp|temp)/[^/]+\.(php\d?|phtml|phar|jsp|aspx?)(\?|$)", re.I), "script dynamique dans répertoire d'upload"),
    (re.compile(r"\.(php\d?|phtml|phar|jsp|aspx?)\?cmd=", re.I), "param cmd= sur script dynamique"),
    (re.compile(r"\?(cmd|exec|command|shell|execute)=", re.I), "param suspect cmd/exec/shell"),
]


def _webshell_match_reason(uri: str) -> str | None:
    u = (uri or "").strip()
    if not u:
        return None
    decoded = _safe_unquote(u)
    combined = u + " " + decoded
    for rx, reason in WEBSHELL_REGEXES:
        if rx.search(combined):
            return reason
    return None


SQLI_VOLUME_WINDOW_SEC: int = 300
SQLI_VOLUME_MIN: int = 20
SQLI_EXFIL_MIN_BYTES: int = 5 * 1024 * 1024  # 5 MB cumulés → signal exfil

_USER_EXEC_RE = re.compile(r"User (\w+) executed:\s*(.+)")
_SSHD_ACCEPTED_RE = re.compile(r"Accepted (?:password|publickey) for (\w+) from ([\d.]+)")
_PRIV_ESC_CMD_RE = re.compile(
    r"(sudo\s+-[il]|useradd|adduser|NOPASSWD|/etc/shadow|/etc/sudoers|chmod\s+[+]s)",
    re.I,
)

# MITRE ATT&CK T1053.003 — Scheduled Task/Job: Cron + T1543 — Create or Modify System Process
PERSISTENCE_REGEXES: list[tuple[str, str]] = [
    (r"crontab\s+-e",          "CRONTAB_EDIT"),
    (r"crontab\s+.*\/tmp",     "CRONTAB_TMP"),
    (r">>.*\/etc\/crontab",    "ETC_CRONTAB_APPEND"),
    (r">>.*\/etc\/cron\.",     "CRON_D_APPEND"),
    (r"systemctl\s+enable",    "SYSTEMCTL_ENABLE"),
    (r">>.*\/etc\/rc\.local",  "RC_LOCAL_APPEND"),
    (r"cp\s+.*\/etc\/init\.d", "INITD_COPY"),
]

# MITRE ATT&CK T1136.001 — Create Account: Local Account + T1098 — Account Manipulation
BACKDOOR_ACCOUNT_REGEXES: list[tuple[str, str]] = [
    (r"useradd\s+\w+",          "USERADD"),
    (r"usermod\s+.*-aG\s+sudo", "USERMOD_SUDO"),
    (r"usermod\s+.*-aG\s+wheel","USERMOD_WHEEL"),
    (r">>\s*\/etc\/passwd",     "PASSWD_APPEND"),
    (r">>\s*\/etc\/sudoers",    "SUDOERS_APPEND"),
    (r"passwd\s+\w+",           "PASSWD_CHANGE"),
]

# MITRE ATT&CK T1070 — Indicator Removal (Clear Command History, Clear Linux Logs)
LOG_TAMPER_REGEXES: list[tuple[str, str]] = [
    (r"history\s+-c",        "HISTORY_CLEAR"),
    (r"rm\s+.*\/var\/log",   "RM_VAR_LOG"),
    (r"truncate\s+-s\s+0",   "TRUNCATE_LOG"),
    (r">\s*\/var\/log",      "REDIRECT_EMPTY_LOG"),
    (r"unset\s+HISTFILE",    "UNSET_HISTFILE"),
    (r"export\s+HISTSIZE=0", "HISTSIZE_ZERO"),
    (r"shred\s+.*log",       "SHRED_LOG"),
]

SSRF_PARAM_RE = re.compile(
    r'(?:url|callback|target|proxy|redirect|fetch|dest(?:ination)?|uri|src|path|resource|endpoint|load|request)\s*=\s*'
    r'((?:https?|file|gopher|dict|ldap|ftp|php|jar)://[^\s&"\']+)',
    re.I,
)

# Aucun scheme non-HTTP n'a d'usage légitime sur un endpoint web fetch
SSRF_DANGEROUS_SCHEME_RE = re.compile(r'^(?:file|gopher|dict|ldap|ftp|php|jar)://', re.I)

SSRF_INTERNAL_RE = re.compile(
    r'^(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.|127\.|169\.254\.|0\.0\.0\.0|localhost|\[::1\]|::1)',
    re.I,
)

TRAVERSAL_RE = re.compile(
    r"(\.\./|\.\.\\|"
    r"%2e%2e[%2f5c/\\]|%252e%252e[%2f5c/\\]?|"
    r"\.\.%2f|\.\.%5c|\.\.%252f|"
    r"%2e%2e%2f|%2e%2e/|"
    r"%c0%ae%c0%ae[%2f5c/\\]?|"  # overlong UTF-8 encoding of ../
    r"\.\.\.\.//|\.\.\.\.\\\\|\.\.\.\/\\)",  # ....// ....\ ..../\
    re.I,
)

SENSITIVE_PATH_RE = re.compile(
    r"(/etc/|\.ssh/|id_rsa|\.htpasswd|/proc/self|/root/|/var/log/|"
    r"[Cc][:/\\]Windows|\.bash_history|web\.config|boot\.ini)",
    re.I,
)

# UA caractéristique de l'outil d'automatisation utilisé pour le path traversal
TRAVERSAL_UA_RE = re.compile(r"python-requests/", re.I)

# Nmap NSE User-Agent — ne varie jamais, zéro faux positif
NMAP_UA_REGEX = re.compile(r"nmap", re.I)

# Nikto scanner User-Agent — toujours "Nikto" dans la chaîne, zéro faux positif
NIKTO_UA_REGEX = re.compile(r"nikto", re.I)

# THC-Hydra User-Agent — présent selon la version/config
HYDRA_UA_REGEX = re.compile(r"hydra", re.I)

# Endpoints login ciblés par les brute forcers HTTP
LOGIN_URI_REGEX = re.compile(
    r"/login|/signin|/admin|/wp-admin|/wp-login\.php"
    r"|/administrator|/auth|/api/(?:login|auth|token)"
    r"|/(?:account|user)/login",
    re.I,
)

# IDOR — accès à des ressources via IDs numériques dans l'URI
IDOR_URI_REGEX = re.compile(
    r"\/api\/users?\/\d+|\/api\/accounts?\/\d+|\/api\/orders?\/\d+"
    r"|\/api\/files?\/\d+|\/api\/documents?\/\d+|\/api\/invoices?\/\d+"
    r"|\?id=\d+|\?user_?id=\d+|\?account_?id=\d+|\?file_?id=\d+",
    re.I,
)

# MITRE ATT&CK T1048.003 — Exfiltration Over Unencrypted Protocol (curl/wget upload)
EXFIL_TOOL_REGEXES: list[tuple[str, str]] = [
    (r"curl\s+.*-T\s+",             "CURL_UPLOAD_T"),
    (r"curl\s+.*--upload-file",     "CURL_UPLOAD_FILE"),
    (r"curl\s+.*-F\s+.*file=@",    "CURL_UPLOAD_FORM"),
    (r"curl\s+.*--data-binary\s+@", "CURL_DATA_BINARY"),
    (r"wget\s+.*--post-file",       "WGET_POST_FILE"),
    (r"wget\s+.*--post-data",       "WGET_POST_DATA"),
    (r"curl\s+.*\/etc\/",           "CURL_ETC"),
    (r"curl\s+.*\.ssh",             "CURL_SSH_DIR"),
    (r"wget\s+.*\/etc\/",           "WGET_ETC"),
]

SQLI_REGEXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"union\s+(all\s+)?select",                   re.I), "UNION SELECT"),
    (re.compile(r"select\s+\*\s+from",                        re.I), "SELECT * FROM"),
    (re.compile(r";\s*drop\s+table",                          re.I), "DROP TABLE"),
    (re.compile(r"--\s*$",                                    re.I), "commentaire --"),
    (re.compile(r"or\s+1\s*=\s*1",                            re.I), "OR 1=1"),
    (re.compile(r"'\s*or\s+'?\d+'?\s*=\s*'?\d+",             re.I), "'OR 1=1'"),
    (re.compile(r"'\s*or\s+'[^']*'\s*=\s*'[^']*'",           re.I), "OR 'a'='a'"),
    (re.compile(r"'\s*#",                                     re.I), "commentaire #"),
    (re.compile(r"sleep\s*\(\s*\d*",                          re.I), "sleep()"),
    (re.compile(r"waitfor\s+delay",                           re.I), "WAITFOR DELAY"),
    (re.compile(r"benchmark\s*\(",                            re.I), "benchmark()"),
    (re.compile(r"pg_sleep\s*\(",                             re.I), "pg_sleep()"),
    (re.compile(r"sqlmap",                                    re.I), "outil sqlmap"),
    (re.compile(r"xp_cmdshell",                               re.I), "xp_cmdshell"),
    (re.compile(r"information_schema",                        re.I), "information_schema"),
    (re.compile(r"select\s+.*\s+from\s+information_schema",   re.I), "dump information_schema"),
    (re.compile(r"load_file\s*\(",                            re.I), "load_file()"),
    (re.compile(r"into\s+outfile",                            re.I), "INTO OUTFILE"),
    (re.compile(r"0x[0-9a-f]{4,}",                            re.I), "payload hex"),
]


def _extract_id(uri: str) -> int | None:
    m = re.search(r"/(\d+)(?:/|$|\?)|[?&]\w*id=(\d+)", uri, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    return None


def _is_sequential(uris: list[str], min_sequential: int = 5) -> bool:
    ids = sorted(filter(None, (_extract_id(u) for u in uris)))
    if len(ids) < min_sequential:
        return False
    consecutive = sum(1 for i in range(len(ids) - 1) if ids[i + 1] - ids[i] == 1)
    return consecutive >= min_sequential - 1


def _sqli_match_reason(uri: str, user_agent: str = "") -> str | None:
    u = (uri or "").strip()
    ua = (user_agent or "").strip()
    if not u and not ua:
        return None
    decoded = _safe_unquote(u)
    combined = (u + " " + decoded + " " + ua).lower()
    for rx, reason in SQLI_REGEXES:
        if rx.search(combined):
            return reason
    return None


def detect_signals_window_1h(
    events: Iterable[NormalizedEvent],
    *,
    # credential stuffing / spray
    cs_failures_threshold: int = 100,
    cs_distinct_users_threshold: int = 10,
    cs_failure_ratio_threshold: float = 0.90,
    # "taux d'échec important vers un même utilisateur"
    cs_user_failures_threshold: int = 50,
    service_user_allowlist: set[str] | None = None,
    # ssrf
    ssrf_min_hits: int = 3,
    # directory traversal
    traversal_min_hits: int = 5,
    traversal_success_min_hits: int = 1,
    # ssh bruteforce
    ssh_failures_threshold: int = 200,
    ssh_burst_n: int = 5,
    ssh_burst_seconds: int = 10,
    # "auth_method exclusivement SSH"
    ssh_exclusive_min_failures: int = 200,
    # "géolocalisation incohérente baseline" (attaquants RU vs legit FR)
    ssh_suspicious_geo: set[str] | None = None,
    ssh_baseline_geo: set[str] | None = None,
    # webshell
    webshell_min_hits: int = 1,
    # reverse shell
    reverse_shell_min_hits: int = 1,
    # sqli
    sqli_min_hits: int = 3,
    sqli_volume_min: int = SQLI_VOLUME_MIN,
    sqli_volume_window_sec: int = SQLI_VOLUME_WINDOW_SEC,
    # "présence d'erreur 500 venant des mêmes IPs" (signal faible)
    sqli_500_threshold: int = 50,
    # exfiltration : cumul des bytes de réponse envoyés à l'IP attaquante
    sqli_exfil_bytes_threshold: int = SQLI_EXFIL_MIN_BYTES,
    # "user-agent contient sqlmap"
    sqli_sqlmap_threshold: int = 1,
    max_evidence_ids: int = 20,
    # port scan
    port_scan_threshold: int = 15,
    burst_window_seconds: int = 10,
    burst_min_ports: int = 10,
    # log tampering
    log_tamper_threshold: int = 1,
    # persistence & backdoor account
    persistence_threshold: int = 1,
    backdoor_account_threshold: int = 1,
    # web scanning
    dir_bruteforce_threshold: int = 50,
    dir_bruteforce_window_sec: int = 300,
    # http brute force
    http_bruteforce_threshold: int = 20,
    http_bruteforce_window_sec: int = 900,
    # IDOR & exfil tools
    idor_threshold: int = 10,
    exfil_tool_threshold: int = 1,
) -> list[Signal]:
    """Deterministic detections on a 1-hour window (MVP).

    Returns a list of `Signal` objects, meant to be fed into an aggregator.
    """
    if service_user_allowlist is None:
        service_user_allowlist = {"monitoring", "backup_svc", "prometheus_svc"}
    if ssh_suspicious_geo is None:
        ssh_suspicious_geo = {"RU", "CN", "KP"}  # Russie, Chine, Corée du Nord
    if ssh_baseline_geo is None:
        ssh_baseline_geo = {"FR"}

    # --- Credential stuffing candidates (auth failures grouped by source_ip) ---
    auth_by_ip: dict[str, list[NormalizedEvent]] = defaultdict(list)
    auth_user_set_by_ip: dict[str, set[str]] = defaultdict(set)
    auth_failures_by_ip: Counter[str] = Counter()
    # "taux d'échec important vers un même utilisateur"
    auth_failures_by_user: Counter[str] = Counter()
    auth_by_user: dict[str, list[NormalizedEvent]] = defaultdict(list)
    # succès auth par IP (ratio + credential stuffing réussi)
    auth_successes_by_ip: dict[str, list[NormalizedEvent]] = defaultdict(list)
    auth_successes_count_by_ip: Counter[str] = Counter()

    # --- SSH bruteforce (auth_method=ssh failures grouped by source_ip) ---
    ssh_failures_by_ip: dict[str, list[datetime]] = defaultdict(list)
    ssh_methods_by_ip: dict[str, Counter[str]] = defaultdict(Counter)

    # --- Géolocalisation par IP (tous log_source confondus) ---
    geo_by_ip: dict[str, Counter[str]] = defaultdict(Counter)

    # --- SSRF hits grouped by (source_ip, hostname) ---
    ssrf_hits: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)  # (ts, uri, target)

    # --- Directory traversal hits grouped by (source_ip, hostname) ---
    traversal_hits: dict[tuple[str, str], list[tuple[str, str, int | None]]] = defaultdict(list)  # (ts, uri, status_code)
    traversal_success_hits: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)  # (ts, uri) for status=200 + sensitive
    traversal_ua_hits: dict[tuple[str, str], int] = defaultdict(int)  # python-requests UA hits

    # --- SQLi hits grouped by (source_ip, hostname) ---
    sqli_hits: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)  # (ts, uri, reason)
    sqli_ts_by_ip: dict[str, list[datetime]] = defaultdict(list)  # pour détection volume automatisé
    sqli_500_by_ip: Counter[str] = Counter()
    sqli_500_ts_by_ip: dict[str, list[str]] = defaultdict(list)
    sqli_sqlmap_by_ip: Counter[str] = Counter()

    # --- Exfil réseau : bytes envoyés VERS une IP externe (dst_ip → [(ts, bytes, src_ip)]) ---
    net_exfil_to_ip: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    # --- Premier event réseau (toute action) par IP externe (recon/scan pré-attaque) ---
    min_net_ts_by_ip: dict[str, str] = {}

    # --- Premier event applicatif par IP (pour ancrer le début de l'incident) ---
    min_app_event_ts_by_ip: dict[str, str] = {}

    # --- System log collectors (priv_esc + lateral movement) ---
    priv_esc_by_user: dict[str, list[tuple[str, str]]] = defaultdict(list)  # user → [(ts, cmd)]
    lateral_move_events: list[tuple[str, str, str, str]] = []               # (ts, src_ip, user, dst_host)

    # --- Webshell hits grouped by (source_ip, hostname) ---
    webshell_hits: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)  # (ts, uri, reason)

    # --- Reverse shell hits grouped by (source_ip, destination_ip) ---
    reverse_shell_hits: dict[tuple[str, str], list[tuple[str, int, str]]] = defaultdict(list)  # (ts, dst_port, reason)

    # --- Port scan hits grouped by (source_ip, destination_ip) ---
    port_scan_ports: dict[tuple[str, str], set[int]] = defaultdict(set)
    port_scan_timestamps: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)  # (ts, port)

    # --- Nmap NSE User-Agent hits grouped by source_ip ---
    nmap_ua_hits: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)  # [(ts, uri, ua)]
    nmap_ua_hostname: dict[str, str] = {}

    # --- Log tampering hits grouped by hostname ---
    log_tamper_by_host: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)  # [(ts, msg, reason)]

    # --- Persistence hits grouped by hostname ---
    persistence_by_host: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)

    # --- Backdoor account hits grouped by hostname ---
    backdoor_account_by_host: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)

    # --- Nikto UA hits grouped by source_ip ---
    nikto_ua_hits: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)  # [(ts, uri, ua)]
    nikto_ua_hostname: dict[str, str] = {}

    # --- Directory bruteforce 404 hits grouped by (source_ip, hostname) ---
    dir_bruteforce_hits: dict[tuple[str, str], list[tuple[str | None, str]]] = defaultdict(list)  # [(ts, uri)]

    # --- HTTP brute force POST 401/403 on login endpoints ---
    http_bruteforce_hits: dict[tuple[str, str], list[tuple[str | None, str, int]]] = defaultdict(list)  # [(ts, uri, status)]

    # --- HTTP brute force success: POST 200 on login endpoints per source_ip ---
    http_bf_login_success: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)  # [(ts, uri, hostname)]

    # --- Hydra UA hits grouped by source_ip ---
    hydra_ua_hits: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)  # [(ts, uri, ua)]
    hydra_ua_hostname: dict[str, str] = {}

    # --- IDOR hits grouped by (source_ip, hostname) ---
    idor_hits: dict[tuple[str, str], list[tuple[str | None, str]]] = defaultdict(list)  # [(ts, uri)]

    # --- Exfil tool hits grouped by hostname ---
    exfil_tool_by_host: dict[str, list[tuple[str | None, str, str]]] = defaultdict(list)  # [(ts, msg, reason)]

    # Helper to capture evidence ids
    def _evidence_id(e: NormalizedEvent) -> str | None:
        return (e.get("raw_ref") or {}).get("raw_id")

    for e in events:
        ts = e.get("timestamp")
        if not ts:
            continue
        src = e.get("source_ip") or ""
        # Les règles auth/app/network nécessitent une source_ip ; system non
        if not src and e.get("log_source") != "system":
            continue

        # Géolocalisation globale (tous log_source)
        geo = e.get("geolocation_country")
        if src and geo:
            geo_by_ip[src][str(geo)] += 1

        # AUTH rules
        if e.get("log_source") == "authentication":
            status = e.get("status")
            user = e.get("username")
            if status == "failure":
                auth_by_ip[src].append(e)
                auth_failures_by_ip[src] += 1
                if user and user not in service_user_allowlist:
                    auth_user_set_by_ip[src].add(user)
                if user and user not in service_user_allowlist:
                    auth_failures_by_user[user] += 1
                    auth_by_user[user].append(e)
            elif status == "success":
                auth_successes_count_by_ip[src] += 1
                if user and user not in service_user_allowlist:
                    auth_successes_by_ip[src].append(e)

            # SSH bruteforce candidates — internal IPs excluded (lateral movement handled by SSH_LATERAL_MOVE)
            method = e.get("auth_method") or ""
            if method and not _is_internal_ip(src):
                ssh_methods_by_ip[src][str(method)] += 1
            if method == "ssh" and status == "failure" and not _is_internal_ip(src):
                ssh_failures_by_ip[src].append(_to_dt(ts))

        # APP rules (SQLi + Webshell + Directory Traversal + Nmap UA)
        if e.get("log_source") == "application":
            uri = e.get("uri") or ""
            host = e.get("hostname") or ""
            ua = e.get("user_agent") or ""
            decoded_uri = _safe_unquote(uri)
            # Nmap NSE User-Agent — single hit is enough, zero false positives
            if NMAP_UA_REGEX.search(ua):
                nmap_ua_hits[src].append((ts, uri, ua))
                if host and src not in nmap_ua_hostname:
                    nmap_ua_hostname[src] = host
            # Nikto scanner User-Agent — single hit is enough, zero false positives
            if NIKTO_UA_REGEX.search(ua):
                nikto_ua_hits[src].append((ts, uri, ua))
                if host and src not in nikto_ua_hostname:
                    nikto_ua_hostname[src] = host
            # Hydra User-Agent
            if HYDRA_UA_REGEX.search(ua):
                hydra_ua_hits[src].append((ts, uri, ua))
                if host and src not in hydra_ua_hostname:
                    hydra_ua_hostname[src] = host
            # Directory bruteforce — volume of 404 from same (ip, host)
            if e.get("status_code") == 404 and host:
                dir_bruteforce_hits[(src, host)].append((ts, uri))
            # HTTP brute force — POST 401/403 or success 200 on login endpoint
            if (e.get("http_method") or "").upper() == "POST" and host and LOGIN_URI_REGEX.search(uri):
                sc = e.get("status_code")
                if sc in (401, 403):
                    http_bruteforce_hits[(src, host)].append((ts, uri, sc))
                elif sc == 200:
                    http_bf_login_success[src].append((ts, uri, host))
            # IDOR — GET 200 on API endpoints with numeric IDs
            if IDOR_URI_REGEX.search(uri) and e.get("status_code") == 200 and host:
                idor_hits[(src, host)].append((ts, uri))
            # SSRF detection
            for m in SSRF_PARAM_RE.finditer(uri + " " + decoded_uri):
                target_url = m.group(1)
                # Scheme dangereux non-HTTP : toujours suspect, pas besoin de vérifier le host
                if SSRF_DANGEROUS_SCHEME_RE.match(target_url):
                    ssrf_hits[(src, host)].append((ts, uri, target_url))
                    break
                # HTTP(S) : vérifier si le host est interne/loopback/metadata
                host_m = re.match(r'https?://([^/\s?#:]+)', target_url)
                if host_m and SSRF_INTERNAL_RE.match(host_m.group(1)):
                    ssrf_hits[(src, host)].append((ts, uri, target_url))
                    break

            # Directory traversal detection
            is_traversal_pattern = bool(TRAVERSAL_RE.search(uri) or TRAVERSAL_RE.search(decoded_uri))
            is_traversal_ua = bool(TRAVERSAL_UA_RE.search(ua))
            is_sensitive = bool(SENSITIVE_PATH_RE.search(decoded_uri) or SENSITIVE_PATH_RE.search(uri))
            # Fire on explicit traversal pattern OR python-requests UA + sensitive path (automated LFI tool)
            if is_traversal_pattern or (is_traversal_ua and is_sensitive):
                sc = e.get("status_code")
                traversal_hits[(src, host)].append((ts, uri, sc))
                if is_traversal_ua:
                    traversal_ua_hits[(src, host)] += 1
                if sc == 200 and is_sensitive:
                    traversal_success_hits[(src, host)].append((ts, uri))
            sqli_reason = _sqli_match_reason(uri, ua)
            if sqli_reason:
                sqli_ts_by_ip[src].append(_to_dt(ts))
                if host:
                    sqli_hits[(src, host)].append((ts, uri, sqli_reason))
            ws_reason = _webshell_match_reason(uri)
            if ws_reason and host:
                webshell_hits[(src, host)].append((ts, uri, ws_reason))
            if not min_app_event_ts_by_ip.get(src) or ts < min_app_event_ts_by_ip[src]:
                min_app_event_ts_by_ip[src] = ts
            if e.get("status_code") == 500 and sqli_reason:
                sqli_500_by_ip[src] += 1
                sqli_500_ts_by_ip[src].append(ts)
            if "sqlmap" in ua.lower():
                sqli_sqlmap_by_ip[src] += 1

        # NETWORK rules (Reverse shell + Exfil + Port scan)
        if e.get("log_source") == "network":
            # Track first network contact for external IPs (recon phase, even if rejected)
            if src and not _is_internal_ip(src):
                if src not in min_net_ts_by_ip or ts < min_net_ts_by_ip[src]:
                    min_net_ts_by_ip[src] = ts
            dst_ip = e.get("destination_ip") or ""
            dst_port = e.get("destination_port")
            # Port scan runs before action filter — dropped/rejected ports are the key signal
            if src and dst_ip and dst_port:
                port_scan_ports[(src, dst_ip)].add(dst_port)
                if ts:
                    port_scan_timestamps[(src, dst_ip)].append((ts, dst_port))
            action = (e.get("action") or "").lower()
            if action in ("block", "drop", "reject", "deny"):
                continue
            if _is_internal_ip(src) and dst_ip and not _is_internal_ip(dst_ip):
                if dst_port in REVERSE_SHELL_PORTS:
                    reason = f"{src} → {dst_ip}:{dst_port}"
                    reverse_shell_hits[(src, dst_ip)].append((ts, dst_port, reason))
                bs = e.get("bytes_sent") or 0
                if bs > 0:
                    net_exfil_to_ip[dst_ip].append((ts, bs, src))

        # SYSTEM rules (priv_esc + lateral movement + log tampering)
        if e.get("log_source") == "system":
            msg = e.get("message") or ""
            host = e.get("hostname") or ""
            m_exec = _USER_EXEC_RE.search(msg)
            if m_exec:
                user, cmd = m_exec.group(1), m_exec.group(2)
                if _PRIV_ESC_CMD_RE.search(cmd):
                    priv_esc_by_user[user].append((ts, cmd))
            m_accepted = _SSHD_ACCEPTED_RE.search(msg)
            if m_accepted:
                user, origin_ip = m_accepted.group(1), m_accepted.group(2)
                if _is_internal_ip(origin_ip):
                    lateral_move_events.append((ts, origin_ip, user, host))
            if host:
                for pattern, reason in LOG_TAMPER_REGEXES:
                    if re.search(pattern, msg, re.IGNORECASE):
                        log_tamper_by_host[host].append((ts, msg, reason))
                        break
                for pattern, reason in PERSISTENCE_REGEXES:
                    if re.search(pattern, msg, re.IGNORECASE):
                        persistence_by_host[host].append((ts, msg, reason))
                        break
                for pattern, reason in BACKDOOR_ACCOUNT_REGEXES:
                    if re.search(pattern, msg, re.IGNORECASE):
                        backdoor_account_by_host[host].append((ts, msg, reason))
                        break
                for pattern, reason in EXFIL_TOOL_REGEXES:
                    if re.search(pattern, msg, re.IGNORECASE):
                        exfil_tool_by_host[host].append((ts, msg, reason))
                        break

    def _is_stuffing_ip(ip: str) -> bool:
        fails = auth_failures_by_ip[ip]
        if fails < cs_failures_threshold:
            return False
        if len(auth_user_set_by_ip[ip]) < cs_distinct_users_threshold:
            return False
        # Exclure les IPs dont tous les échecs sont via SSH (SSH bruteforce, pas stuffing)
        methods = ssh_methods_by_ip.get(ip)
        if methods and methods.get("ssh", 0) >= fails:
            return False
        total = fails + auth_successes_count_by_ip[ip]
        return (fails / total) >= cs_failure_ratio_threshold

    # IPs qui ont déclenché CREDENTIAL_STUFFING dans cette fenêtre
    stuffing_ips: set[str] = {ip for ip in auth_failures_by_ip if _is_stuffing_ip(ip)}

    signals: list[Signal] = []

    # --- Emit CREDENTIAL_STUFFING signals ---
    for ip in stuffing_ips:
        fails = auth_failures_by_ip[ip]
        distinct_users = len(auth_user_set_by_ip[ip])
        ev_ids: list[str] = []
        for ev in auth_by_ip[ip]:
            rid = _evidence_id(ev)
            if rid:
                ev_ids.append(rid)
            if len(ev_ids) >= max_evidence_ids:
                break
        ts_list = [
            ev.get("timestamp") for ev in auth_by_ip[ip] if ev.get("timestamp")
        ]
        sig_ts = min(ts_list) if ts_list else None
        sig_ts_end = max(ts_list) if ts_list else None
        # Anchor start to recon phase if network events precede auth
        net_ts = min_net_ts_by_ip.get(ip)
        if net_ts and (sig_ts is None or net_ts < sig_ts):
            sig_ts = net_ts
        if sig_ts:
            signals.append(
                {
                    "rule_id": "CREDENTIAL_STUFFING",
                    "ts": sig_ts,
                    "ts_end": sig_ts_end,
                    "source_ip": ip,
                    "iocs": {
                        "failures": int(fails),
                        "distinct_usernames": int(distinct_users),
                        "window_seconds": WINDOW_SECONDS,
                    },
                    "evidence_ids": ev_ids,
                }
            )

    # --- Emit CREDENTIAL_STUFFING_BY_USER signals (many failures to same username) ---
    # Seulement si au moins un des échecs provient d'une IP de stuffing
    for user, fails in auth_failures_by_user.items():
        if fails < cs_user_failures_threshold:
            continue
        ips_for_user = {e.get("source_ip") for e in auth_by_user[user]}
        if not ips_for_user & stuffing_ips:
            continue
        stuffing_evs = [e for e in auth_by_user[user] if e.get("source_ip") in stuffing_ips]
        ev_ids: list[str] = []
        for ev in stuffing_evs:
            rid = _evidence_id(ev)
            if rid:
                ev_ids.append(rid)
            if len(ev_ids) >= max_evidence_ids:
                break
        ts_list = [ev.get("timestamp") for ev in stuffing_evs if ev.get("timestamp")]
        sig_ts = min(ts_list) if ts_list else None
        sig_ts_end = max(ts_list) if ts_list else None
        if sig_ts:
            signals.append(
                {
                    "rule_id": "CREDENTIAL_STUFFING_USER_TARGETED",
                    "ts": sig_ts,
                    "ts_end": sig_ts_end,
                    "username": user,
                    "iocs": {"failures": int(fails), "window_seconds": WINDOW_SECONDS},
                    "evidence_ids": ev_ids,
                }
            )

    # --- Emit CREDENTIAL_STUFFING_SUCCESS signals ---
    for ip, successes in auth_successes_by_ip.items():
        # ne garder que les succès depuis une IP qui a elle-même déclenché CREDENTIAL_STUFFING
        if ip not in stuffing_ips:
            continue
        relevant = successes
        if not relevant:
            continue
        compromised_users = list({e.get("username") for e in relevant if e.get("username")})
        ev_ids = []
        for ev in relevant:
            rid = _evidence_id(ev)
            if rid:
                ev_ids.append(rid)
            if len(ev_ids) >= max_evidence_ids:
                break
        failure_ts_list = [ev.get("timestamp") for ev in auth_by_ip[ip] if ev.get("timestamp")]
        sig_ts = min(failure_ts_list) if failure_ts_list else None
        success_ts_list = [ev.get("timestamp") for ev in relevant if ev.get("timestamp")]
        sig_ts_end = max(success_ts_list) if success_ts_list else sig_ts
        if sig_ts:
            signals.append(
                {
                    "rule_id": "CREDENTIAL_STUFFING_SUCCESS",
                    "ts": sig_ts,
                    "ts_end": sig_ts_end,
                    "source_ip": ip,
                    "iocs": {
                        "failures_before": int(auth_failures_by_ip[ip]),
                        "successes": int(len(relevant)),
                        "compromised_usernames": compromised_users,
                        "window_seconds": WINDOW_SECONDS,
                    },
                    "evidence_ids": ev_ids,
                }
            )

    # --- Emit SSH_BRUTEFORCE signals ---
    for ip, dts in ssh_failures_by_ip.items():
        if len(dts) < ssh_failures_threshold:
            # still emit if bursty (human-impossible cadence)
            dts_sorted = sorted(dts)
            burst = False
            j = 0
            for i in range(len(dts_sorted)):
                while dts_sorted[i] - dts_sorted[j] > timedelta(seconds=ssh_burst_seconds):
                    j += 1
                if i - j + 1 >= ssh_burst_n:
                    burst = True
                    break
            if not burst:
                continue

        dts_sorted = sorted(dts)
        sig_ts = dts_sorted[0].isoformat().replace("+00:00", "Z")
        sig_ts_end = dts_sorted[-1].isoformat().replace("+00:00", "Z")
        signals.append(
            {
                "rule_id": "SSH_BRUTEFORCE",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "iocs": {
                    "ssh_failures": int(len(dts)),
                    "window_seconds": WINDOW_SECONDS,
                    "burst_n": ssh_burst_n,
                    "burst_seconds": ssh_burst_seconds,
                },
            }
        )

    # IPs ayant déclenché SSH_BRUTEFORCE (utilisées pour filtrer priv_esc / exfil)
    def _is_ssh_bf_ip(ip: str) -> bool:
        dts = ssh_failures_by_ip.get(ip, [])
        if not dts:
            return False
        if len(dts) >= ssh_failures_threshold:
            return True
        dts_s = sorted(dts)
        j = 0
        for i in range(len(dts_s)):
            while (dts_s[i] - dts_s[j]).total_seconds() > ssh_burst_seconds:
                j += 1
            if i - j + 1 >= ssh_burst_n:
                return True
        return False

    ssh_bf_ips: set[str] = {ip for ip in ssh_failures_by_ip if _is_ssh_bf_ip(ip)}
    ssh_targeted_users: set[str] = {
        u for ip in ssh_bf_ips for u in auth_user_set_by_ip.get(ip, set())
    }

    # --- Emit SSH_PRIV_ESC signals ---
    for user, priv_esc_evs in priv_esc_by_user.items():
        if user not in ssh_targeted_users:
            continue
        evs = sorted(priv_esc_evs)
        sig_ts, sig_ts_end = evs[0][0], evs[-1][0]
        signals.append(
            {
                "rule_id": "SSH_PRIV_ESC",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "username": user,
                "iocs": {
                    "commands": [cmd for _, cmd in evs[:10]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SSH_LATERAL_MOVE signals ---
    if lateral_move_events and ssh_bf_ips:
        evs = sorted(lateral_move_events)
        sig_ts, sig_ts_end = evs[0][0], evs[-1][0]
        targets = list({host for _, _, _, host in evs})
        src_ips = list({ip for _, ip, _, _ in evs})
        signals.append(
            {
                "rule_id": "SSH_LATERAL_MOVE",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "iocs": {
                    "lateral_targets": targets,
                    "pivot_ips": src_ips,
                    "hits": len(evs),
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SYS_LOG_TAMPERING signals ---
    for hostname, hits in log_tamper_by_host.items():
        if len(hits) < log_tamper_threshold:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0] or "")
        sig_ts = hits_sorted[0][0] or "1970-01-01T00:00:00Z"
        sig_ts_end = hits_sorted[-1][0] or sig_ts
        signals.append(
            {
                "rule_id": "SYS_LOG_TAMPERING",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "hostname": hostname,
                "iocs": {
                    "hits": len(hits),
                    "reasons": list({h[2] for h in hits}),
                    "sample_messages": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit KILL_CHAIN_COMPROMISE_AND_COVER (log tampering post-compromise) ---
    _COMPROMISE_RULES: frozenset[str] = frozenset({
        "SSH_PRIV_ESC", "SSH_LATERAL_MOVE", "WEB_WEBSHELL", "NET_REVERSE_SHELL",
    })
    compromised_hosts: set[str] = {
        s["hostname"] for s in signals
        if s["rule_id"] in _COMPROMISE_RULES and s.get("hostname")
    }
    for signal in list(signals):
        if signal["rule_id"] == "SYS_LOG_TAMPERING" and signal.get("hostname") in compromised_hosts:
            signals.append(
                {
                    "rule_id": "KILL_CHAIN_COMPROMISE_AND_COVER",
                    "ts": signal.get("ts", "1970-01-01T00:00:00Z"),
                    "ts_end": signal.get("ts_end", "1970-01-01T00:00:00Z"),
                    "hostname": signal["hostname"],
                    "iocs": {
                        "cover_rule": "SYS_LOG_TAMPERING",
                        "description": "Effacement de traces sur host déjà compromis",
                        "window_seconds": WINDOW_SECONDS,
                    },
                }
            )

    # --- Emit SYS_PERSISTENCE signals ---
    for hostname, hits in persistence_by_host.items():
        if len(hits) < persistence_threshold:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0] or "")
        sig_ts = hits_sorted[0][0] or "1970-01-01T00:00:00Z"
        sig_ts_end = hits_sorted[-1][0] or sig_ts
        signals.append(
            {
                "rule_id": "SYS_PERSISTENCE",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "hostname": hostname,
                "iocs": {
                    "hits": len(hits),
                    "reasons": list({h[2] for h in hits}),
                    "sample_messages": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SYS_BACKDOOR_ACCOUNT signals ---
    for hostname, hits in backdoor_account_by_host.items():
        if len(hits) < backdoor_account_threshold:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0] or "")
        sig_ts = hits_sorted[0][0] or "1970-01-01T00:00:00Z"
        sig_ts_end = hits_sorted[-1][0] or sig_ts
        reasons = {h[2] for h in hits}
        full_sequence = (
            any(r in reasons for r in {"USERADD", "PASSWD_APPEND"})
            and any(r in reasons for r in {"USERMOD_SUDO", "USERMOD_WHEEL", "SUDOERS_APPEND"})
        )
        signals.append(
            {
                "rule_id": "SYS_BACKDOOR_ACCOUNT",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "hostname": hostname,
                "iocs": {
                    "hits": len(hits),
                    "reasons": list(reasons),
                    "full_sequence_detected": full_sequence,
                    "sample_messages": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit KILL_CHAIN_PERSISTENCE (persistence/backdoor post-compromise) ---
    _PERSISTENCE_RULES: frozenset[str] = frozenset({"SYS_PERSISTENCE", "SYS_BACKDOOR_ACCOUNT"})
    _COMPROMISE_RULES_FOR_PERSIST: frozenset[str] = frozenset({
        "SSH_PRIV_ESC", "SSH_LATERAL_MOVE", "WEB_WEBSHELL", "NET_REVERSE_SHELL", "SYS_LOG_TAMPERING",
    })
    compromised_hosts_persist: set[str] = {
        s["hostname"] for s in signals
        if s["rule_id"] in _COMPROMISE_RULES_FOR_PERSIST and s.get("hostname")
    }
    already_correlated_persistence: set[str] = set()
    for signal in list(signals):
        if (
            signal["rule_id"] in _PERSISTENCE_RULES
            and signal.get("hostname") in compromised_hosts_persist
            and signal.get("hostname") not in already_correlated_persistence
        ):
            already_correlated_persistence.add(signal["hostname"])
            signals.append(
                {
                    "rule_id": "KILL_CHAIN_PERSISTENCE",
                    "ts": signal.get("ts", "1970-01-01T00:00:00Z"),
                    "ts_end": signal.get("ts_end", "1970-01-01T00:00:00Z"),
                    "hostname": signal["hostname"],
                    "iocs": {
                        "persistence_rule": signal["rule_id"],
                        "description": "Persistence établie sur host compromis",
                        "window_seconds": WINDOW_SECONDS,
                    },
                }
            )

    # --- Emit SYS_EXFIL_TOOL signals ---
    for hostname, hits in exfil_tool_by_host.items():
        if len(hits) < exfil_tool_threshold:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0] or "")
        sig_ts = hits_sorted[0][0] or "1970-01-01T00:00:00Z"
        sig_ts_end = hits_sorted[-1][0] or sig_ts
        signals.append(
            {
                "rule_id": "SYS_EXFIL_TOOL",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "hostname": hostname,
                "iocs": {
                    "hits": len(hits),
                    "reasons": list({h[2] for h in hits}),
                    "sample_messages": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit KILL_CHAIN_SHELL_TO_EXFIL (exfil via curl/wget post-compromise) ---
    _SHELL_RULES: frozenset[str] = frozenset({
        "SSH_PRIV_ESC", "WEB_WEBSHELL", "NET_REVERSE_SHELL",
        "SYS_BACKDOOR_ACCOUNT", "SYS_PERSISTENCE",
    })
    compromised_hosts_exfil: set[str] = {
        s["hostname"] for s in signals
        if s["rule_id"] in _SHELL_RULES and s.get("hostname")
    }
    already_correlated_exfil: set[str] = set()
    for signal in list(signals):
        if (
            signal["rule_id"] == "SYS_EXFIL_TOOL"
            and signal.get("hostname") in compromised_hosts_exfil
            and signal.get("hostname") not in already_correlated_exfil
        ):
            already_correlated_exfil.add(signal["hostname"])
            signals.append(
                {
                    "rule_id": "KILL_CHAIN_SHELL_TO_EXFIL",
                    "ts": signal.get("ts", "1970-01-01T00:00:00Z"),
                    "ts_end": signal.get("ts_end", "1970-01-01T00:00:00Z"),
                    "hostname": signal["hostname"],
                    "iocs": {
                        "exfil_rule": "SYS_EXFIL_TOOL",
                        "description": "Exfiltration via curl/wget depuis host compromis",
                        "window_seconds": WINDOW_SECONDS,
                    },
                }
            )

    # --- Emit SSH_EXFIL signals ---
    for ip in ssh_bf_ips:
        events = net_exfil_to_ip.get(ip)
        if not events:
            continue
        total_bytes = sum(bs for _, bs, _ in events)
        if total_bytes < sqli_exfil_bytes_threshold:
            continue
        evs = sorted(events, key=lambda x: x[0])
        sig_ts, sig_ts_end = evs[0][0], evs[-1][0]
        internal_srcs = list({s for _, _, s in evs})
        signals.append(
            {
                "rule_id": "SSH_EXFIL",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "iocs": {
                    "exfil_bytes": int(total_bytes),
                    "exfil_mb": round(total_bytes / 1_048_576, 2),
                    "internal_sources": internal_srcs,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SSH_BRUTEFORCE_EXCLUSIVE_METHOD signals (auth_method exclusively ssh) ---
    for ip, methods in ssh_methods_by_ip.items():
        total = sum(methods.values())
        if total <= 0:
            continue
        ssh_only = methods.get("ssh", 0) == total
        if ssh_only and methods.get("ssh", 0) >= ssh_exclusive_min_failures:
            ip_evs = auth_by_ip.get(ip) or [{}]
            ip_ts = [ev.get("timestamp") for ev in ip_evs if ev.get("timestamp")]
            signals.append(
                {
                    "rule_id": "SSH_BRUTEFORCE_SSH_ONLY",
                    "ts": min(ip_ts) if ip_ts else "1970-01-01T00:00:00Z",
                    "ts_end": max(ip_ts) if ip_ts else "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {
                        "auth_methods": dict(methods),
                        "window_seconds": WINDOW_SECONDS,
                    },
                }
            )

    # --- Emit SUSPICIOUS_GEO signals (tous log_source) ---
    for ip, geos in geo_by_ip.items():
        suspicious_hits = sum(geos.get(c, 0) for c in ssh_suspicious_geo)
        if (
            suspicious_hits > 0
            and not any(geos.get(c, 0) > 0 for c in ssh_baseline_geo)
            and sum(geos.values()) >= 10
        ):
            ip_evs = auth_by_ip.get(ip) or [{}]
            ip_ts = [ev.get("timestamp") for ev in ip_evs if ev.get("timestamp")]
            signals.append(
                {
                    "rule_id": "SUSPICIOUS_GEO",
                    "ts": min(ip_ts) if ip_ts else "1970-01-01T00:00:00Z",
                    "ts_end": max(ip_ts) if ip_ts else "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {
                        "geo_counts": dict(geos),
                        "suspicious_countries": list(ssh_suspicious_geo),
                        "baseline": list(ssh_baseline_geo),
                        "window_seconds": WINDOW_SECONDS,
                    },
                }
            )

    # --- Emit SSRF signals ---
    for (ip, host), hits in ssrf_hits.items():
        if len(hits) < ssrf_min_hits:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts = hits_sorted[0][0]
        sig_ts_end = hits_sorted[-1][0]
        targets = list({t for _, _, t in hits_sorted})
        # extract distinct target hosts and categorize
        target_hosts: list[str] = []
        dangerous_schemes: list[str] = []
        metadata_hits = 0
        loopback_hits = 0
        seen: set[str] = set()
        for t in targets:
            if SSRF_DANGEROUS_SCHEME_RE.match(t):
                scheme = t.split("://")[0].lower()
                if scheme not in dangerous_schemes:
                    dangerous_schemes.append(scheme)
                continue
            hm = re.match(r'https?://([^/\s?#:]+)', t)
            if hm:
                h = hm.group(1)
                if h not in seen:
                    seen.add(h)
                    target_hosts.append(h)
                if "169.254" in h:
                    metadata_hits += sum(1 for _, _, tt in hits_sorted if "169.254" in tt)
                if re.match(r'^(?:127\.|localhost|0\.0\.0\.0|\[::1\]|::1)', h, re.I):
                    loopback_hits += sum(1 for _, _, tt in hits_sorted if h in tt)
        iocs: dict = {
            "hits": int(len(hits_sorted)),
            "ssrf_targets": target_hosts[:10],
            "sample_uris": [u for _, u, _ in hits_sorted[:5]],
            "window_seconds": WINDOW_SECONDS,
        }
        if dangerous_schemes:
            iocs["dangerous_schemes"] = dangerous_schemes
        if metadata_hits:
            iocs["cloud_metadata_hits"] = int(metadata_hits)
        if loopback_hits:
            iocs["loopback_hits"] = int(loopback_hits)
        signals.append(
            {
                "rule_id": "SSRF",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "hostname": host,
                "iocs": iocs,
            }
        )

    # --- Emit DIRECTORY_TRAVERSAL signals ---
    for (ip, host), hits in traversal_hits.items():
        if len(hits) < traversal_min_hits:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts = hits_sorted[0][0]
        sig_ts_end = hits_sorted[-1][0]
        status_counts: Counter[int | None] = Counter(sc for _, _, sc in hits_sorted)
        success_hits = status_counts.get(200, 0)
        sample_uris = [u for _, u, _ in hits_sorted[:5]]
        ua_hits = traversal_ua_hits.get((ip, host), 0)
        sig = {
            "rule_id": "DIRECTORY_TRAVERSAL",
            "ts": sig_ts,
            "ts_end": sig_ts_end,
            "source_ip": ip,
            "hostname": host,
            "iocs": {
                "hits": int(len(hits_sorted)),
                "successful_reads": int(success_hits),
                "status_counts": {str(k): v for k, v in status_counts.most_common()},
                "sample_uris": sample_uris,
                "window_seconds": WINDOW_SECONDS,
                **({"python_requests_ua_hits": int(ua_hits)} if ua_hits else {}),
            },
        }
        # attach sensitive file reads if any
        suc = traversal_success_hits.get((ip, host))
        if suc:
            suc_sorted = sorted(suc, key=lambda x: x[0])
            sig["iocs"]["sensitive_files"] = list({_safe_unquote(u) for _, u in suc_sorted})[:10]
        signals.append(sig)

    # --- Emit DIRECTORY_TRAVERSAL_SUCCESS signals (sensitive files confirmed read) ---
    for (ip, host), hits in traversal_success_hits.items():
        if len(hits) < traversal_success_min_hits:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts = hits_sorted[0][0]
        sig_ts_end = hits_sorted[-1][0]
        sensitive_files = list({_safe_unquote(u) for _, u in hits_sorted})[:10]
        signals.append(
            {
                "rule_id": "DIRECTORY_TRAVERSAL_SUCCESS",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "hostname": host,
                "iocs": {
                    "successful_reads": int(len(hits_sorted)),
                    "sensitive_files": sensitive_files,
                    "window_seconds": WINDOW_SECONDS,
                    **({"python_requests_ua_hits": int(traversal_ua_hits.get((ip, host), 0))} if traversal_ua_hits.get((ip, host)) else {}),
                },
            }
        )

    # --- Emit SQL_INJECTION signals ---
    for (ip, host), hits in sqli_hits.items():
        if len(hits) < sqli_min_hits:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts, _, _ = hits_sorted[0]
        sig_ts_end, _, _ = hits_sorted[-1]
        top_reasons = Counter([r for _, _, r in hits_sorted]).most_common(5)
        top_uris = [u for _, u, _ in hits_sorted[:5]]
        signals.append(
            {
                "rule_id": "SQL_INJECTION",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "hostname": host,
                "iocs": {
                    "hits": int(len(hits_sorted)),
                    "top_reasons": top_reasons,
                    "sample_uris": top_uris,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit WEB_SQLI_AUTOMATED signals ---
    for ip, dts in sqli_ts_by_ip.items():
        dts_sorted = sorted(dts)
        j = 0
        burst_start = None
        for i in range(len(dts_sorted)):
            while (dts_sorted[i] - dts_sorted[j]).total_seconds() > sqli_volume_window_sec:
                j += 1
            if i - j + 1 >= sqli_volume_min:
                burst_start = dts_sorted[j]
                break
        if burst_start is None:
            continue
        sig_ts = dts_sorted[0].isoformat().replace("+00:00", "Z")
        sig_ts_end = dts_sorted[-1].isoformat().replace("+00:00", "Z")
        signals.append(
            {
                "rule_id": "WEB_SQLI_AUTOMATED",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "iocs": {
                    "sqli_hits": int(len(dts_sorted)),
                    "volume_window_sec": sqli_volume_window_sec,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit WEB_WEBSHELL signals ---
    for (ip, host), hits in webshell_hits.items():
        if len(hits) < webshell_min_hits:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts, _, _ = hits_sorted[0]
        sig_ts_end, _, _ = hits_sorted[-1]
        top_reasons = Counter([r for _, _, r in hits_sorted]).most_common(5)
        sample_uris = [u for _, u, _ in hits_sorted[:5]]
        signals.append(
            {
                "rule_id": "WEB_WEBSHELL",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "hostname": host,
                "iocs": {
                    "hits": int(len(hits_sorted)),
                    "top_reasons": top_reasons,
                    "sample_uris": sample_uris,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit NET_REVERSE_SHELL signals ---
    for (src_ip, dst_ip), hits in reverse_shell_hits.items():
        if len(hits) < reverse_shell_min_hits:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0])
        sig_ts, _, _ = hits_sorted[0]
        sig_ts_end, _, _ = hits_sorted[-1]
        ports = list({port for _, port, _ in hits_sorted})
        signals.append(
            {
                "rule_id": "NET_REVERSE_SHELL",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "iocs": {
                    "destination_ip": dst_ip,
                    "destination_ports": ports,
                    "hits": int(len(hits_sorted)),
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SQL_INJECTION_MANY_500 signals (probe par 500 avec SQLi dans l'URI) ---
    for ip, n500 in sqli_500_by_ip.items():
        if n500 < sqli_500_threshold:
            continue
        ts_list = sqli_500_ts_by_ip[ip]
        sig_ts = min(ts_list) if ts_list else "1970-01-01T00:00:00Z"
        sig_ts_end = max(ts_list) if ts_list else sig_ts
        signals.append(
            {
                "rule_id": "SQL_INJECTION_MANY_500",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "iocs": {
                    "status_code_500": int(n500),
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SQL_INJECTION_EXFIL signals ---
    # Pour chaque IP ayant déclenché SQL_INJECTION, vérifier si des serveurs internes
    # ont envoyé un volume significatif de données vers cette IP (exfil réseau).
    sqli_ips = {ip for ip, _ in sqli_hits}
    for ip in sqli_ips:
        events = net_exfil_to_ip.get(ip)
        if not events:
            continue
        total_bytes = sum(bs for _, bs, _ in events)
        if total_bytes < sqli_exfil_bytes_threshold:
            continue
        events_sorted = sorted(events, key=lambda x: x[0])
        sig_ts = min_app_event_ts_by_ip.get(ip) or events_sorted[0][0]
        sig_ts_end = events_sorted[-1][0]
        internal_srcs = list({src for _, _, src in events_sorted})
        signals.append(
            {
                "rule_id": "SQL_INJECTION_EXFIL",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": ip,
                "iocs": {
                    "exfil_bytes": int(total_bytes),
                    "exfil_mb": round(total_bytes / 1_048_576, 2),
                    "internal_sources": internal_srcs,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit SQL_INJECTION_SQLMAP_UA signals (strong indicator) ---
    for ip, n in sqli_sqlmap_by_ip.items():
        if n >= sqli_sqlmap_threshold:
            signals.append(
                {
                    "rule_id": "SQL_INJECTION_SQLMAP_UA",
                    "ts": "1970-01-01T00:00:00Z",
                    "source_ip": ip,
                    "iocs": {"sqlmap_hits": int(n), "window_seconds": WINDOW_SECONDS},
                }
            )

    # --- Emit NET_PORT_SCAN signals ---
    for (src_ip, dst_ip), ports in port_scan_ports.items():
        if len(ports) < port_scan_threshold:
            continue
        ts_port_pairs = port_scan_timestamps.get((src_ip, dst_ip), [])
        ts_list = [t for t, _ in ts_port_pairs if t]
        sig_ts = min(ts_list) if ts_list else "1970-01-01T00:00:00Z"
        sig_ts_end = max(ts_list) if ts_list else sig_ts
        signals.append(
            {
                "rule_id": "NET_PORT_SCAN",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": dst_ip,
                "iocs": {
                    "distinct_ports_count": int(len(ports)),
                    "sample_ports": sorted(list(ports))[:20],
                    "threshold": port_scan_threshold,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit NET_NMAP_USERAGENT signals ---
    for src_ip, hits in nmap_ua_hits.items():
        hits_with_ts = [(t, u, a) for t, u, a in hits if t]
        if not hits_with_ts:
            continue
        sig_ts = min(t for t, _, _ in hits_with_ts)
        sig_ts_end = max(t for t, _, _ in hits_with_ts)
        signals.append(
            {
                "rule_id": "NET_NMAP_USERAGENT",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": nmap_ua_hostname.get(src_ip),
                "iocs": {
                    "hits": int(len(hits)),
                    "user_agent": hits[0][2],
                    "sample_uris": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit WEB_NIKTO_SCAN signals ---
    for src_ip, hits in nikto_ua_hits.items():
        hits_with_ts = [(t, u, a) for t, u, a in hits if t]
        sig_ts = min(t for t, _, _ in hits_with_ts) if hits_with_ts else "1970-01-01T00:00:00Z"
        sig_ts_end = max(t for t, _, _ in hits_with_ts) if hits_with_ts else sig_ts
        signals.append(
            {
                "rule_id": "WEB_NIKTO_SCAN",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": nikto_ua_hostname.get(src_ip),
                "iocs": {
                    "hits": len(hits),
                    "user_agent": hits[0][2],
                    "sample_uris": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit WEB_DIR_BRUTEFORCE signals (burst of 404 within a short window) ---
    for (src_ip, hostname), hits in dir_bruteforce_hits.items():
        parsed_bf: list[tuple[datetime, str]] = []
        for ts_str, uri in hits:
            if not ts_str:
                continue
            try:
                parsed_bf.append((_to_dt(ts_str), uri))
            except Exception:
                continue
        if not parsed_bf:
            continue
        parsed_bf.sort(key=lambda x: x[0])
        j = 0
        burst_start = None
        for i in range(len(parsed_bf)):
            while (parsed_bf[i][0] - parsed_bf[j][0]).total_seconds() > dir_bruteforce_window_sec:
                j += 1
            if i - j + 1 >= dir_bruteforce_threshold:
                burst_start = j
                break
        if burst_start is None:
            continue
        sig_ts = parsed_bf[burst_start][0].isoformat().replace("+00:00", "Z")
        sig_ts_end = parsed_bf[-1][0].isoformat().replace("+00:00", "Z")
        signals.append(
            {
                "rule_id": "WEB_DIR_BRUTEFORCE",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": hostname,
                "iocs": {
                    "hits_404": len(parsed_bf),
                    "sample_uris": [u for _, u in parsed_bf[burst_start:burst_start + 10]],
                    "threshold": dir_bruteforce_threshold,
                    "burst_window_sec": dir_bruteforce_window_sec,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit NET_PORT_SCAN_BURST signals (fast scans -T4/-T5) ---
    for (src_ip, dst_ip), ts_port_pairs in port_scan_timestamps.items():
        parsed_burst: list[tuple[datetime, int]] = []
        for ts_str, port in ts_port_pairs:
            if not ts_str:
                continue
            try:
                parsed_burst.append((_to_dt(ts_str), port))
            except Exception:
                continue
        if not parsed_burst:
            continue
        parsed_burst.sort(key=lambda x: x[0])
        for i in range(len(parsed_burst)):
            t_start = parsed_burst[i][0]
            ports_in_window: set[int] = set()
            for j in range(i, len(parsed_burst)):
                if (parsed_burst[j][0] - t_start).total_seconds() <= burst_window_seconds:
                    ports_in_window.add(parsed_burst[j][1])
                else:
                    break
            if len(ports_in_window) >= burst_min_ports:
                sig_ts = t_start.isoformat().replace("+00:00", "Z")
                sig_ts_end = parsed_burst[-1][0].isoformat().replace("+00:00", "Z")
                signals.append(
                    {
                        "rule_id": "NET_PORT_SCAN_BURST",
                        "ts": sig_ts,
                        "ts_end": sig_ts_end,
                        "source_ip": src_ip,
                        "hostname": dst_ip,
                        "iocs": {
                            "ports_in_burst": int(len(ports_in_window)),
                            "burst_window_seconds": burst_window_seconds,
                            "window_seconds": WINDOW_SECONDS,
                        },
                    }
                )
                break  # one signal per (src, dst) pair

    # --- Collect port_scan_ips for kill chain correlation ---
    port_scan_ips: set[str] = set()
    for (src_ip, _), ports in port_scan_ports.items():
        if len(ports) >= port_scan_threshold:
            port_scan_ips.add(src_ip)
    port_scan_ips |= set(nmap_ua_hits.keys())

    # --- Emit KILL_CHAIN_RECON_TO_EXPLOIT signals ---
    if port_scan_ips:
        _EXPLOIT_RULES: frozenset[str] = frozenset({
            "SQL_INJECTION", "WEB_SQLI_AUTOMATED",
            "SSH_BRUTEFORCE", "SSH_BRUTEFORCE_SSH_ONLY",
            "CREDENTIAL_STUFFING",
            "DIRECTORY_TRAVERSAL", "DIRECTORY_TRAVERSAL_SUCCESS",
            "WEB_WEBSHELL", "SSRF", "NET_REVERSE_SHELL",
        })
        already_correlated: set[str] = set()
        for signal in list(signals):
            ip = signal.get("source_ip")
            if (
                signal["rule_id"] in _EXPLOIT_RULES
                and ip in port_scan_ips
                and ip not in already_correlated
            ):
                already_correlated.add(ip)
                signals.append(
                    {
                        "rule_id": "KILL_CHAIN_RECON_TO_EXPLOIT",
                        "ts": signal.get("ts", ""),
                        "ts_end": signal.get("ts_end", ""),
                        "source_ip": ip,
                        "hostname": signal.get("hostname"),
                        "iocs": {
                            "recon_rule": "NET_PORT_SCAN",
                            "exploit_rule": signal["rule_id"],
                            "description": "Scan réseau suivi d'une exploitation dans la même fenêtre",
                            "window_seconds": WINDOW_SECONDS,
                        },
                    }
                )

    # --- Emit WEB_BRUTEFORCE_HTTP signals (sliding window) ---
    for (src_ip, hostname), hits in http_bruteforce_hits.items():
        parsed_hbf: list[tuple[datetime, str, int]] = []
        for ts_str, uri_h, sc in hits:
            if not ts_str:
                continue
            try:
                parsed_hbf.append((_to_dt(ts_str), uri_h, sc))
            except Exception:
                continue
        if not parsed_hbf:
            continue
        parsed_hbf.sort(key=lambda x: x[0])
        j = 0
        burst_start = None
        for i in range(len(parsed_hbf)):
            while (parsed_hbf[i][0] - parsed_hbf[j][0]).total_seconds() > http_bruteforce_window_sec:
                j += 1
            if i - j + 1 >= http_bruteforce_threshold:
                burst_start = j
                break
        if burst_start is None:
            continue
        sig_ts = parsed_hbf[burst_start][0].isoformat().replace("+00:00", "Z")
        sig_ts_end = parsed_hbf[-1][0].isoformat().replace("+00:00", "Z")
        signals.append(
            {
                "rule_id": "WEB_BRUTEFORCE_HTTP",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": hostname,
                "iocs": {
                    "hits": len(parsed_hbf),
                    "target_uris": list({u for _, u, _ in parsed_hbf}),
                    "status_codes": list({sc for _, _, sc in parsed_hbf}),
                    "threshold": http_bruteforce_threshold,
                    "window_seconds": http_bruteforce_window_sec,
                },
            }
        )

    # --- Emit WEB_BRUTEFORCE_HTTP_UA signals ---
    for src_ip, hits in hydra_ua_hits.items():
        hits_with_ts = [(t, u, a) for t, u, a in hits if t]
        sig_ts = min(t for t, _, _ in hits_with_ts) if hits_with_ts else "1970-01-01T00:00:00Z"
        sig_ts_end = max(t for t, _, _ in hits_with_ts) if hits_with_ts else sig_ts
        signals.append(
            {
                "rule_id": "WEB_BRUTEFORCE_HTTP_UA",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": hydra_ua_hostname.get(src_ip),
                "iocs": {
                    "hits": len(hits),
                    "user_agent": hits[0][2],
                    "sample_uris": [h[1] for h in hits[:5]],
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit WEB_BRUTEFORCE_HTTP_SUCCESS signals ---
    bf_http_ips: set[str] = {
        s["source_ip"] for s in signals
        if s["rule_id"] == "WEB_BRUTEFORCE_HTTP" and s.get("source_ip")
    }
    bf_http_ips |= set(hydra_ua_hits.keys())
    already_bf_success: set[str] = set()
    for src_ip, successes in http_bf_login_success.items():
        if src_ip not in bf_http_ips or src_ip in already_bf_success:
            continue
        already_bf_success.add(src_ip)
        successes_sorted = sorted(successes, key=lambda x: x[0] or "")
        sig_ts = successes_sorted[0][0] or "1970-01-01T00:00:00Z"
        sig_ts_end = successes_sorted[-1][0] or sig_ts
        signals.append(
            {
                "rule_id": "WEB_BRUTEFORCE_HTTP_SUCCESS",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": successes_sorted[0][2] or None,
                "iocs": {
                    "success_uri": successes_sorted[0][1],
                    "description": "Brute force HTTP réussi — login obtenu",
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit KILL_CHAIN_WEBBRUTEFORCE_TO_EXPLOIT signals ---
    web_bruteforce_ips: set[str] = bf_http_ips.copy()
    if web_bruteforce_ips:
        _WEBBF_EXPLOIT_RULES: frozenset[str] = frozenset({
            "WEB_WEBSHELL", "SQL_INJECTION", "DIRECTORY_TRAVERSAL_SUCCESS",
            "NET_REVERSE_SHELL", "SSRF",
        })
        already_correlated_bf: set[str] = set()
        for signal in list(signals):
            ip = signal.get("source_ip")
            if (
                signal["rule_id"] in _WEBBF_EXPLOIT_RULES
                and ip in web_bruteforce_ips
                and ip not in already_correlated_bf
            ):
                already_correlated_bf.add(ip)
                signals.append(
                    {
                        "rule_id": "KILL_CHAIN_WEBBRUTEFORCE_TO_EXPLOIT",
                        "ts": signal.get("ts", "1970-01-01T00:00:00Z"),
                        "ts_end": signal.get("ts_end", "1970-01-01T00:00:00Z"),
                        "source_ip": ip,
                        "hostname": signal.get("hostname"),
                        "iocs": {
                            "bruteforce_rule": "WEB_BRUTEFORCE_HTTP",
                            "exploit_rule": signal["rule_id"],
                            "description": "Brute force web suivi d'une exploitation",
                            "window_seconds": WINDOW_SECONDS,
                        },
                    }
                )

    # --- Emit WEB_IDOR signals ---
    for (src_ip, hostname), hits in idor_hits.items():
        if len(hits) < idor_threshold:
            continue
        hits_sorted = sorted(hits, key=lambda x: x[0] or "")
        sig_ts = hits_sorted[0][0] or "1970-01-01T00:00:00Z"
        sig_ts_end = hits_sorted[-1][0] or sig_ts
        uris = [h[1] for h in hits_sorted]
        signals.append(
            {
                "rule_id": "WEB_IDOR",
                "ts": sig_ts,
                "ts_end": sig_ts_end,
                "source_ip": src_ip,
                "hostname": hostname,
                "iocs": {
                    "hits": len(hits_sorted),
                    "sequential_ids_detected": _is_sequential(uris),
                    "sample_uris": uris[:10],
                    "threshold": idor_threshold,
                    "window_seconds": WINDOW_SECONDS,
                },
            }
        )

    # --- Emit KILL_CHAIN_WEBSCAN_TO_EXPLOIT signals ---
    web_scan_ips: set[str] = set(nikto_ua_hits.keys())
    web_scan_ips |= {
        s["source_ip"] for s in signals
        if s["rule_id"] == "WEB_DIR_BRUTEFORCE" and s.get("source_ip")
    }
    if web_scan_ips:
        _WEBSCAN_EXPLOIT_RULES: frozenset[str] = frozenset({
            "SQL_INJECTION", "WEB_SQLI_AUTOMATED",
            "DIRECTORY_TRAVERSAL", "DIRECTORY_TRAVERSAL_SUCCESS",
            "WEB_WEBSHELL", "SSRF", "NET_REVERSE_SHELL",
        })
        already_correlated_webscan: set[str] = set()
        for signal in list(signals):
            ip = signal.get("source_ip")
            if (
                signal["rule_id"] in _WEBSCAN_EXPLOIT_RULES
                and ip in web_scan_ips
                and ip not in already_correlated_webscan
            ):
                already_correlated_webscan.add(ip)
                signals.append(
                    {
                        "rule_id": "KILL_CHAIN_WEBSCAN_TO_EXPLOIT",
                        "ts": signal.get("ts", "1970-01-01T00:00:00Z"),
                        "ts_end": signal.get("ts_end", "1970-01-01T00:00:00Z"),
                        "source_ip": ip,
                        "hostname": signal.get("hostname"),
                        "iocs": {
                            "scan_rule": "WEB_NIKTO_SCAN or WEB_DIR_BRUTEFORCE",
                            "exploit_rule": signal["rule_id"],
                            "description": "Scan web suivi d'une exploitation dans la même fenêtre",
                            "window_seconds": WINDOW_SECONDS,
                        },
                    }
                )

    return signals
