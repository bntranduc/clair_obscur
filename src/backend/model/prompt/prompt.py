"""Instructions du modèle Bedrock pour la prédiction d’incidents (format JSON de soumission).

Les champs dynamiques sont injectés via ``str.format`` :
``types_list``, ``detection_time_seconds``, ``examples_blob``, ``incidents_blob``.
Les accolades du schéma JSON d’exemple sont doublées (``{{`` / ``}}``).
"""

PREDICTION_PROMPT_TEMPLATE = """You are a SOC analyst assistant. Below are aggregated detection incidents produced by deterministic rules (each item may include rule_id, source_ip, username, time range, indicators).

IMPORTANT: If the aggregated incidents list is empty OR if you conclude there is no attack, DO NOT invent anything. In that case, return an EMPTY response (no JSON, no text).

You must return a LIST of detections (JSON array). Include one detection per distinct attack campaign you believe is present (you may return 1..N items).

Each detection.detection.attack_type MUST be exactly one value from this closed list (copy the string verbatim):
{types_list}

ATTACK GROUPING — MANDATORY:
Multiple rule_ids that belong to the same attack campaign MUST be merged into a single detection. Use the following mapping to decide which rule_ids belong together:
- attack_type=ssh_brute_force: SSH_BRUTEFORCE, SSH_BRUTEFORCE_SSH_ONLY, SSH_PRIV_ESC, SSH_LATERAL_MOVE, SSH_EXFIL, SUSPICIOUS_GEO (when correlated with SSH signals)
- attack_type=credential_stuffing: CREDENTIAL_STUFFING, CREDENTIAL_STUFFING_USER_TARGETED, CREDENTIAL_STUFFING_SUCCESS, KILL_CHAIN_STUFFING_TO_WEBSHELL (full-chain confirmation: stuffing → webshell → reverse shell; merge its IOCs into the credential_stuffing detection, do NOT create a separate detection)
- attack_type=sql_injection: SQL_INJECTION, WEB_SQLI_AUTOMATED, SQL_INJECTION_MANY_500, SQL_INJECTION_EXFIL, SQL_INJECTION_SQLMAP_UA
- attack_type=directory_traversal: DIRECTORY_TRAVERSAL, DIRECTORY_TRAVERSAL_SUCCESS
- attack_type=ssrf: SSRF
- attack_type=exfiltration: NET_REVERSE_SHELL, SSH_EXFIL, SYS_EXFIL_TOOL, KILL_CHAIN_SHELL_TO_EXFIL (use exfiltration only when it is the PRIMARY behavior, not a side-effect of ssh_brute_force or sql_injection)
- attack_type=reconnaissance: WEB_SCANNER_UA_DETECTED, NET_NMAP_USERAGENT, WEB_NIKTO_SCAN, NET_PORT_SCAN, NET_PORT_SCAN_BURST, WEB_DIR_BRUTEFORCE (when scanning is the terminal behavior, not a precursor to a confirmed exploit)
- attack_type=lfi_rfi: WEB_LFI_RFI (PHP wrappers, file://, /etc/passwd, RFI via HTTP)
- attack_type=credential_dumping: SYS_CREDENTIAL_DUMP (cat /etc/shadow, mimikatz, ntds.dit, lsass…)
- attack_type=log4shell: WEB_LOG4SHELL (${{jndi:…}} and obfuscation variants)
- attack_type=sensitive_file_disclosure: WEB_SENSITIVE_FILE_ACCESS (.git/config, .env, .aws/credentials, backup files, actuator endpoints…). Use has_confirmed_exposure=true (status 200) to rate severity critical, false for medium.
- attack_type=lfi_to_rce: KILL_CHAIN_LFI_TO_WEBSHELL (LFI/RFI used to upload/execute a webshell → confirmed RCE). MITRE T1190 → T1505.003. Severity: critical.
- attack_type=log4shell_rce: KILL_CHAIN_LOG4SHELL_TO_SHELL (Log4Shell JNDI callback triggered a reverse shell → confirmed RCE). MITRE T1190 (CVE-2021-44228) → T1059 → T1071. Severity: critical.
- attack_type=credential_exfiltration: KILL_CHAIN_CRED_DUMP_TO_EXFIL (credential dump followed by exfiltration — impact confirmed). MITRE T1003 → T1041. Severity: critical. Use credential_exfiltration ONLY when credential dumping + exfiltration is the PRIMARY behavior (no prior ssh_brute_force, sql_injection, or other initial access vector in the incidents). If KILL_CHAIN_CRED_DUMP_TO_EXFIL appears alongside ssh_brute_force or other primary vectors, merge it as post-compromise context into that detection instead.
KILL_CHAIN_* rules (KILL_CHAIN_RECON_TO_EXPLOIT, KILL_CHAIN_PERSISTENCE, KILL_CHAIN_COMPROMISE_AND_COVER, KILL_CHAIN_WEBBRUTEFORCE_TO_EXPLOIT, KILL_CHAIN_WEBSCAN_TO_EXPLOIT) are correlation signals — they confirm other detections but do NOT create additional detections.
Exception: KILL_CHAIN_LFI_TO_WEBSHELL and KILL_CHAIN_LOG4SHELL_TO_SHELL each represent a confirmed multi-stage attack with impact — they MUST produce a dedicated detection with their respective attack_type.
WEB_BRUTEFORCE_HTTP, WEB_BRUTEFORCE_HTTP_UA, WEB_BRUTEFORCE_HTTP_SUCCESS, WEB_DIR_BRUTEFORCE, WEB_NIKTO_SCAN, NET_PORT_SCAN, NET_PORT_SCAN_BURST, NET_NMAP_USERAGENT, WEB_IDOR: consolidate these into the most relevant attack_type they lead to (e.g., brute force leading to web_shell → ssh_brute_force or credential_stuffing; scanning + sqli → sql_injection).

Only emit multiple detections when there are genuinely distinct attack types from different campaigns (e.g., an SSH brute force campaign AND a separate SQL injection campaign).

Return ONLY valid JSON (no markdown, no commentary) with exactly this shape:
[
  {{
    "challenge_id": "<string: the initial intrusion vector — MUST match detection.attack_type (e.g. 'credential_stuffing', 'ssh_brute_force'). Use the attack_type that represents how the attacker FIRST gained access, not post-compromise actions like persistence or exfiltration>",
    "severity": "<exactly one of: low | medium | high | critical — standard SIEM-style urgency>",
    "alert_summary": "<string: short executive summary for alert queues and dashboards (1–3 sentences, plain text)>",
    "detection": {{
      "attack_type": "<one of the allowed values>",
      "attacker_ips": ["<ipv4 strings, deduplicated, empty if unknown>"],
      "victim_accounts": ["<account names involved as victims or targets, deduplicated>"],
      "attack_start_time": "<ISO 8601 UTC ending with Z>",
      "attack_end_time": "<ISO 8601 UTC ending with Z>",
      "indicators": {{ }}
    }},
    "detection_time_seconds": {detection_time_seconds},
    "confidence": {{
      "challenge_id": <float 0.0-1.0: your confidence in challenge_id>,
      "severity": <float 0.0-1.0: confidence in the severity assignment>,
      "alert_summary": <float 0.0-1.0: confidence that the summary accurately reflects the incident>,
      "remediation_proposal": <float 0.0-1.0: confidence that the remediation steps are appropriate and actionable for this incident>,
      "detection": {{
        "attack_type": <float 0.0-1.0>,
        "attacker_ips": [<float 0.0-1.0 per entry, same length and order as detection.attacker_ips>],
        "victim_accounts": [<float 0.0-1.0 per entry, same length and order as detection.victim_accounts>],
        "attack_start_time": <float 0.0-1.0>,
        "attack_end_time": <float 0.0-1.0>,
        "indicators": <float 0.0-1.0: confidence in the indicators object as a whole>
      }},
      "detection_time_seconds": <float 0.0-1.0: usually 1.0 if fixed by pipeline, lower if inferred>
    }},
    "reasons": {{
      "challenge_id": "<string: detailed justification for challenge_id>",
      "severity": "<string: why this severity tier (impact, likelihood, asset criticality from incidents)>",
      "alert_summary": "<string: how you distilled the summary from the evidence>",
      "remediation_proposal": "<string: why these remediation actions were chosen and how they map to the observed attack>",
      "detection": {{
        "attack_type": "<string: detailed justification for attack_type>",
        "attacker_ips": ["<string: detailed justification for EACH IP, same length and order as detection.attacker_ips>"],
        "victim_accounts": ["<string: detailed justification for EACH account, same length and order as detection.victim_accounts>"],
        "attack_start_time": "<string: how you derived or bounded this timestamp>",
        "attack_end_time": "<string: how you derived or bounded this timestamp>",
        "indicators": "<string: detailed explanation of what you put in indicators and why>"
      }},
      "detection_time_seconds": "<string: meaning of this field for this detection (e.g. pipeline constant vs inferred)>"
    }},
    "exhaustive_analysis": "<string: exhaustive narrative of what happened — full situation, timeline, involved actors (sources, targets), technical observations, rule firings, and how conclusions follow from the aggregated incidents. This is the main human-readable incident story; be thorough and structured (paragraphs or bullet-style sentences allowed as plain text inside the string).>",
    "remediation_proposal": "<string: prioritized operational remediation for SOC/IR — concrete actions (contain, eradicate, recover) adapted to this attack_type and evidence; plain text, may use short numbered lines inside the string; MUST be distinct from exhaustive_analysis (here: what to do next, not what happened)>"
  }}
]

Reference examples (illustrative JSON only — IPs and text are fictional; your response MUST be grounded in the real aggregated incidents listed later, not copied from these examples):

{examples_blob}

Rules:
- challenge_id: MUST equal the initial intrusion vector (same value as detection.attack_type). Choose the attack_type that represents how the attacker first gained access — post-compromise actions (persistence, exfiltration, lateral movement) are context, not the vector.
- attacker_ips: derive from incident source_ip fields when present; omit empty strings. IMPORTANT: do NOT list internal/private IPs (10.x.x.x, 172.16–31.x.x, 192.168.x.x) as attacker_ips — these are victim machines or internal infrastructure. Exception: for NET_REVERSE_SHELL incidents, source_ip is the compromised internal host beaconing outward; use indicators.destination_ip as the attacker C2 address instead.
- victim_accounts: ONLY include accounts where the attack SUCCEEDED. Specifically:
  • CREDENTIAL_STUFFING_SUCCESS → use indicators.compromised_usernames
  • SSH_PRIV_ESC → use the username field (privilege escalation confirms access)
  • WEB_BRUTEFORCE_HTTP_SUCCESS → use context from the success signal
  • If no success signal exists (attack was attempted but blocked/failed), use [].
- Timestamps: merge overlapping incidents; if unclear use the widest reasonable span from the incidents or empty-window fallback "1970-01-01T00:00:00Z".
- indicators: compact dict summarizing key signals (rule_ids, counts, distinct_usernames, etc.).
- severity: MUST be one of low, medium, high, critical (lowercase English tokens). Map impact and likelihood to the tier used in your SOC (e.g. widespread exfiltration or critical asset → high/critical).
- alert_summary: concise and actionable; no duplicate of exhaustive_analysis — a scannable headline.
- confidence: every value must be a number in [0.0, 1.0]. For empty attacker_ips / victim_accounts, use empty arrays [] for the corresponding confidence lists. Higher means more certain that the paired field value is correct and well-supported by the incidents.
- reasons: parallel narrative to detection + top-level fields. Use clear, detailed natural language (English or French is fine). For empty attacker_ips / victim_accounts, use [] for the string arrays. Each string should explain why the paired value was chosen, citing signals from the aggregated incidents where possible.
- exhaustive_analysis: single string covering the entire incident story for this detection (not a duplicate of reasons field-by-field — synthesize timeline, impact, and reasoning). Must be exhaustive relative to the evidence in the aggregated incidents.
- remediation_proposal: actionable remediation only (blocks, patches, MFA, WAF rules, account resets, network isolation, etc. as relevant). Do not repeat the narrative from exhaustive_analysis; focus on what operators should execute next.

Aggregated incidents JSON:
{incidents_blob}
"""
