#!/usr/bin/env python3
"""
Agent VM CLAIR OBSCUR — lit nginx + auth, normalise en JSONL, envoie vers S3.

Config : /etc/clair-obscur/vm-agent.env
  RAW_LOGS_BUCKET, RAW_LOGS_PREFIX, AWS_REGION, VM_ID (optionnel)
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3

# Permet d'exécuter depuis vm_setup/agent sans package installé
_AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_AGENT_DIR))

from parsers.auth import parse_auth_line  # noqa: E402
from parsers.nginx_access import parse_nginx_access_line  # noqa: E402

ENV_FILE = Path(os.getenv("VM_AGENT_ENV", "/etc/clair-obscur/vm-agent.env"))
STATE_DIR = Path(os.getenv("VM_AGENT_STATE_DIR", "/var/lib/clair-vm-agent"))
NGINX_LOG = Path(os.getenv("VM_NGINX_ACCESS_LOG", "/var/log/nginx/access.log"))
AUTH_LOG = Path(os.getenv("VM_AUTH_LOG", "/var/log/secure"))
INTERVAL_SEC = int(os.getenv("VM_SHIP_INTERVAL_SEC", "60"))


def hostname() -> str:
    return (os.getenv("VM_ID") or "").strip() or socket.gethostname()


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val


def load_offsets() -> dict[str, int]:
    p = STATE_DIR / "offsets.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_offsets(offsets: dict[str, int]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "offsets.json").write_text(json.dumps(offsets, indent=2), encoding="utf-8")


def tail_file(path: Path, offsets: dict[str, int]) -> list[str]:
    key = str(path)
    start = int(offsets.get(key, 0))
    if not path.is_file():
        return []
    size = path.stat().st_size
    if start > size:
        start = 0
    with path.open("rb") as f:
        f.seek(start)
        data = f.read()
        offsets[key] = f.tell()
    return data.decode("utf-8", errors="replace").splitlines()


def collect_events(offsets: dict[str, int]) -> list[dict]:
    events: list[dict] = []
    for line in tail_file(NGINX_LOG, offsets):
        ev = parse_nginx_access_line(line, hostname=hostname())
        if ev:
            events.append(ev)
    auth_path = AUTH_LOG
    if not auth_path.is_file():
        alt = Path("/var/log/auth.log")
        auth_path = alt if alt.is_file() else auth_path
    for line in tail_file(auth_path, offsets):
        ev = parse_auth_line(line, hostname=hostname())
        if ev:
            events.append(ev)
    return events


def s3_key(prefix: str) -> str:
    p = prefix.rstrip("/") + "/"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_host = hostname().replace("/", "_").replace(" ", "_")
    return f"{p}vms/{safe_host}/{safe_host}-{ts}.jsonl"


def ship(events: list[dict]) -> str | None:
    if not events:
        return None

    ship_mode = (os.getenv("SHIP_MODE") or "").strip().lower()
    api_token = (os.getenv("VM_API_TOKEN") or "").strip()
    api_base = (os.getenv("API_BASE") or "").strip().rstrip("/")

    if ship_mode == "api" or (api_token and api_base):
        return _ship_via_api(events, api_base=api_base, api_token=api_token)

    bucket = (os.getenv("RAW_LOGS_BUCKET") or "").strip()
    prefix = (os.getenv("RAW_LOGS_PREFIX") or "raw/opensearch/logs-raw/").strip()
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    if not bucket:
        raise RuntimeError("RAW_LOGS_BUCKET requis dans vm-agent.env (ou SHIP_MODE=api)")

    body = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
    key = s3_key(prefix)
    client = boto3.client("s3", region_name=region)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return f"s3://{bucket}/{key}"


def _ship_via_api(events: list[dict], *, api_base: str, api_token: str) -> str:
    if not api_base or not api_token:
        raise RuntimeError("API_BASE et VM_API_TOKEN requis pour SHIP_MODE=api")
    import urllib.error
    import urllib.request

    payload = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        f"{api_base}/api/v1/vms/ship",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API ship failed ({e.code}): {body[:500]}") from e
    uri = data.get("s3_uri") or "api"
    return str(uri)


def main() -> None:
    load_env_file(ENV_FILE)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    offsets = load_offsets()
    events = collect_events(offsets)
    save_offsets(offsets)
    if events:
        uri = ship(events)
        print(f"shipped {len(events)} events → {uri}", flush=True)
    else:
        print("no new events", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        while True:
            try:
                main()
            except Exception as e:  # noqa: BLE001
                print(f"error: {e}", file=sys.stderr, flush=True)
            time.sleep(INTERVAL_SEC)
    else:
        main()
