from __future__ import annotations

from typing import Literal, TypedDict


LogKind = Literal["application", "authentication", "network", "system"]
AuthResult = Literal["success", "failure"]


# -----------------------------
# Raw (_source) log shapes (one TypedDict per log_source)
# -----------------------------


class ApplicationFields(TypedDict, total=False):
    timestamp: str
    log_source: LogKind  # "application"

    source_ip: str
    http_method: str
    uri: str
    status_code: int
    response_size: int
    response_time_ms: int
    user_agent: str
    referer: str | None
    hostname: str


class AuthenticationFields(TypedDict, total=False):
    timestamp: str
    log_source: LogKind  # "authentication"

    source_ip: str
    username: str
    auth_method: str
    status: AuthResult
    hostname: str
    session_id: str
    failure_reason: str | None
    geolocation_lat: float
    geolocation_lon: float
    geolocation_country: str


class NetworkFields(TypedDict, total=False):
    timestamp: str
    log_source: LogKind  # "network"

    source_ip: str
    source_port: int
    destination_ip: str
    destination_port: int
    protocol: str
    action: str
    bytes_sent: int
    bytes_received: int
    packets: int
    duration_ms: int


class SystemFields(TypedDict, total=False):
    timestamp: str
    log_source: LogKind  # "system"

    hostname: str
    process: str
    pid: int
    facility: str
    severity: str
    message: str



class RawRef(TypedDict, total=False):
    """Pointer to the original raw record for debugging/replay."""

    raw_id: str
    s3_key: str
    line: int


class NormalizedEvent(TypedDict, total=False):
    """Normalized log with a fixed set of keys.

    The intent is to always return the same keys (missing values as None) so the
    rest of the pipeline can be simple. `raw_ref` is kept for traceability.
    """

    # Traceability
    raw_ref: RawRef

    # Core
    timestamp: str | None
    log_source: LogKind | None

    # Authentication
    auth_method: str | None
    status: AuthResult | None
    session_id: str | None
    failure_reason: str | None
    username: str | None
    geolocation_lat: float | None
    geolocation_lon: float | None
    geolocation_country: str | None

    # Application (HTTP)
    http_method: str | None
    uri: str | None
    status_code: int | None
    response_size: int | None
    response_time_ms: int | None
    user_agent: str | None
    referer: str | None

    # Network
    source_ip: str | None
    source_port: int | None
    destination_ip: str | None
    destination_port: int | None
    protocol: str | None
    action: str | None
    bytes_sent: int | None
    bytes_received: int | None
    packets: int | None
    duration_ms: int | None

    # System
    hostname: str | None
    process: str | None
    pid: int | None
    facility: str | None
    severity: str | None
    message: str | None

