from __future__ import annotations

from typing import Any

from .types import (
    AuthFields,
    HttpFields,
    LogKind,
    NetFields,
    NormalizedEvent,
    RawRef,
    SystemFields,
)


def _common(raw: dict[str, Any], kind: LogKind, raw_ref: RawRef | None) -> NormalizedEvent:
    out: NormalizedEvent = {
        "ts": raw["timestamp"],
        "kind": kind,
    }
    if raw_ref:
        out["raw_ref"] = raw_ref
    if isinstance(raw.get("source_ip"), str):
        out["src_ip"] = raw["source_ip"]
    if isinstance(raw.get("hostname"), str):
        out["host"] = raw["hostname"]
    return out


def normalize_authentication(raw: dict[str, Any], raw_ref: RawRef | None = None) -> NormalizedEvent:
    out = _common(raw, "authentication", raw_ref)

    if isinstance(raw.get("username"), str):
        out["username"] = raw["username"]

    status = raw.get("status")
    if status in ("success", "failure"):
        out["result"] = status  # type: ignore[assignment]

    auth: AuthFields = {}
    if isinstance(raw.get("auth_method"), str):
        auth["auth_method"] = raw["auth_method"]
    if isinstance(raw.get("session_id"), str):
        auth["session_id"] = raw["session_id"]
    if "failure_reason" in raw:
        auth["failure_reason"] = raw.get("failure_reason")
    if isinstance(raw.get("geolocation_lat"), (int, float)):
        auth["geolocation_lat"] = float(raw["geolocation_lat"])
    if isinstance(raw.get("geolocation_lon"), (int, float)):
        auth["geolocation_lon"] = float(raw["geolocation_lon"])
    if isinstance(raw.get("geolocation_country"), str):
        auth["geolocation_country"] = raw["geolocation_country"]

    if auth:
        out["auth"] = auth
    return out


def normalize_application(raw: dict[str, Any], raw_ref: RawRef | None = None) -> NormalizedEvent:
    out = _common(raw, "application", raw_ref)

    http: HttpFields = {}
    if isinstance(raw.get("http_method"), str):
        http["method"] = raw["http_method"]
    if isinstance(raw.get("uri"), str):
        http["uri"] = raw["uri"]
    if isinstance(raw.get("status_code"), int):
        http["status_code"] = raw["status_code"]
    if isinstance(raw.get("response_size"), int):
        http["response_size"] = raw["response_size"]
    if isinstance(raw.get("response_time_ms"), int):
        http["response_time_ms"] = raw["response_time_ms"]
    if isinstance(raw.get("user_agent"), str):
        http["user_agent"] = raw["user_agent"]
    if "referer" in raw:
        if raw.get("referer") is None or isinstance(raw.get("referer"), str):
            http["referer"] = raw.get("referer")

    if http:
        out["http"] = http
    return out


def normalize_network(raw: dict[str, Any], raw_ref: RawRef | None = None) -> NormalizedEvent:
    out = _common(raw, "network", raw_ref)

    if isinstance(raw.get("destination_ip"), str):
        out["dst_ip"] = raw["destination_ip"]
    if isinstance(raw.get("source_port"), int):
        out["src_port"] = raw["source_port"]
    if isinstance(raw.get("destination_port"), int):
        out["dst_port"] = raw["destination_port"]

    net: NetFields = {}
    if isinstance(raw.get("protocol"), str):
        net["protocol"] = raw["protocol"]
    if isinstance(raw.get("action"), str):
        net["action"] = raw["action"]
    if isinstance(raw.get("bytes_sent"), int):
        net["bytes_sent"] = raw["bytes_sent"]
    if isinstance(raw.get("bytes_received"), int):
        net["bytes_received"] = raw["bytes_received"]
    if isinstance(raw.get("packets"), int):
        net["packets"] = raw["packets"]
    if isinstance(raw.get("duration_ms"), int):
        net["duration_ms"] = raw["duration_ms"]

    if net:
        out["net"] = net
    return out


def normalize_system(raw: dict[str, Any], raw_ref: RawRef | None = None) -> NormalizedEvent:
    out = _common(raw, "system", raw_ref)

    system: SystemFields = {}
    if isinstance(raw.get("process"), str):
        system["process"] = raw["process"]
    if isinstance(raw.get("pid"), int):
        system["pid"] = raw["pid"]
    if isinstance(raw.get("facility"), str):
        system["facility"] = raw["facility"]
    if isinstance(raw.get("severity"), str):
        system["severity"] = raw["severity"]
    if isinstance(raw.get("message"), str):
        system["message"] = raw["message"]

    if system:
        out["system"] = system
    return out

