"""Registre des VMs connectées (approbation admin + préfixe S3 par VM)."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

from backend.aws.dynamodb_normalized_logs import _aws_session, _jsonify_for_api

VmStatus = Literal["pending", "approved", "rejected", "revoked"]

PK = "VM_REGISTRY"


def default_vms_table_name() -> str:
    return (os.getenv("DYNAMODB_VMS_TABLE") or "vm-registry").strip() or "vm-registry"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ddb_document(v: Any) -> Any:
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: _ddb_document(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [_ddb_document(x) for x in v if x is not None]
    return v


def _s3_prefix_for_vm(vm_id: str) -> str:
    base = (os.getenv("RAW_LOGS_PREFIX") or "raw/opensearch/logs-raw/").strip()
    if not base.endswith("/"):
        base += "/"
    return f"{base}vms/{vm_id}/"


def _item_to_vm(item: dict[str, Any]) -> dict[str, Any]:
    out = _jsonify_for_api(dict(item))
    out.pop("api_token_hash", None)
    out["vm_id"] = out.get("sk") or item.get("sk")
    return out


def register_vm(
    *,
    hostname: str,
    fingerprint: str = "",
    metadata: dict[str, Any] | None = None,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Enregistre une VM en attente d'approbation. Retourne le token en clair (une seule fois)."""
    host = (hostname or "").strip()
    if not host:
        raise ValueError("hostname requis")

    vm_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    table = table_name or default_vms_table_name()
    item: dict[str, Any] = {
        "pk": PK,
        "sk": vm_id,
        "vm_id": vm_id,
        "hostname": host,
        "fingerprint": (fingerprint or "").strip(),
        "status": "pending",
        "api_token_hash": _hash_token(token),
        "registered_at": _now_iso(),
        "metadata": metadata or {},
    }

    session = _aws_session(region)
    session.resource("dynamodb").Table(table).put_item(Item=_ddb_document(item))

    vm = _item_to_vm(item)
    vm["api_token"] = token
    return vm


def get_vm_by_id(
    vm_id: str,
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any] | None:
    table = table_name or default_vms_table_name()
    session = _aws_session(region)
    resp = session.resource("dynamodb").Table(table).get_item(Key={"pk": PK, "sk": vm_id})
    item = resp.get("Item")
    if not item:
        return None
    return _item_to_vm(item)


def get_vm_by_token(
    token: str,
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any] | None:
    """Scan par hash de token (volume faible : registre VM)."""
    if not (token or "").strip():
        return None
    h = _hash_token(token.strip())
    table = table_name or default_vms_table_name()
    session = _aws_session(region)
    tbl = session.resource("dynamodb").Table(table)
    kwargs: dict[str, Any] = {"KeyConditionExpression": Key("pk").eq(PK)}
    while True:
        resp = tbl.query(**kwargs)
        for item in resp.get("Items") or []:
            if item.get("api_token_hash") == h:
                return _item_to_vm(item)
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return None


def list_all_vms(
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> list[dict[str, Any]]:
    table = table_name or default_vms_table_name()
    session = _aws_session(region)
    tbl = session.resource("dynamodb").Table(table)
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("pk").eq(PK),
    }
    while True:
        resp = tbl.query(**kwargs)
        items.extend(resp.get("Items") or [])
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    vms = [_item_to_vm(it) for it in items]
    vms.sort(key=lambda v: str(v.get("registered_at") or ""), reverse=True)
    return vms


def _update_vm_status(
    vm_id: str,
    *,
    status: VmStatus,
    region: str | None = None,
    table_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    table = table_name or default_vms_table_name()
    session = _aws_session(region)
    tbl = session.resource("dynamodb").Table(table)
    now = _now_iso()
    expr_names: dict[str, str] = {"#s": "status"}
    expr_vals: dict[str, Any] = {":s": status}
    sets = ["#s = :s"]

    if status == "approved":
        prefix = _s3_prefix_for_vm(vm_id)
        sets.extend(["approved_at = :a", "s3_prefix = :p"])
        expr_vals[":a"] = now
        expr_vals[":p"] = prefix
        expr_vals[":n"] = None
        sets.append("rejected_at = :n")
        sets.append("revoked_at = :n")
    elif status == "rejected":
        sets.extend(["rejected_at = :r"])
        expr_vals[":r"] = now
    elif status == "revoked":
        sets.extend(["revoked_at = :r"])
        expr_vals[":r"] = now

    if extra:
        for k, v in extra.items():
            placeholder = f"#{k}"
            val_key = f":{k}"
            expr_names[placeholder] = k
            expr_vals[val_key] = v
            sets.append(f"{placeholder} = {val_key}")

    tbl.update_item(
        Key={"pk": PK, "sk": vm_id},
        UpdateExpression="SET " + ", ".join(sets),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_vals,
        ConditionExpression="attribute_exists(sk)",
    )
    vm = get_vm_by_id(vm_id, region=region, table_name=table)
    if vm is None:
        raise ValueError(f"VM {vm_id} introuvable après mise à jour")
    return vm


def approve_vm(
    vm_id: str,
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    vm = get_vm_by_id(vm_id, region=region, table_name=table_name)
    if vm is None:
        raise LookupError(f"VM {vm_id} introuvable")
    if vm.get("status") == "approved":
        return vm
    return _update_vm_status(vm_id, status="approved", region=region, table_name=table_name)


def reject_vm(
    vm_id: str,
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    vm = get_vm_by_id(vm_id, region=region, table_name=table_name)
    if vm is None:
        raise LookupError(f"VM {vm_id} introuvable")
    return _update_vm_status(vm_id, status="rejected", region=region, table_name=table_name)


def revoke_vm(
    vm_id: str,
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    vm = get_vm_by_id(vm_id, region=region, table_name=table_name)
    if vm is None:
        raise LookupError(f"VM {vm_id} introuvable")
    return _update_vm_status(vm_id, status="revoked", region=region, table_name=table_name)


def touch_last_ship(
    vm_id: str,
    *,
    region: str | None = None,
    table_name: str | None = None,
) -> None:
    table = table_name or default_vms_table_name()
    session = _aws_session(region)
    session.resource("dynamodb").Table(table).update_item(
        Key={"pk": PK, "sk": vm_id},
        UpdateExpression="SET last_ship_at = :t",
        ExpressionAttributeValues={":t": _now_iso()},
    )


def create_s3_prefix_marker(
    vm_id: str,
    *,
    bucket: str | None = None,
    region: str | None = None,
) -> str:
    """Crée un marqueur objet dans le bucket pour le préfixe VM."""
    b = (bucket or os.getenv("RAW_LOGS_BUCKET") or "").strip()
    if not b:
        raise ValueError("RAW_LOGS_BUCKET requis")
    prefix = _s3_prefix_for_vm(vm_id)
    key = f"{prefix}.keep"
    r = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    session = _aws_session(r)
    session.client("s3").put_object(
        Bucket=b,
        Key=key,
        Body=b"clair-obscur vm prefix marker\n",
        ContentType="text/plain",
    )
    return f"s3://{b}/{prefix}"


def ship_events_to_s3(
    vm: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    bucket: str | None = None,
    region: str | None = None,
) -> str:
    """Écrit un batch JSONL dans le préfixe S3 de la VM approuvée."""
    if vm.get("status") != "approved":
        raise PermissionError("VM non approuvée")
    prefix = str(vm.get("s3_prefix") or "").strip()
    if not prefix:
        raise ValueError("s3_prefix manquant pour cette VM")

    b = (bucket or os.getenv("RAW_LOGS_BUCKET") or "").strip()
    if not b:
        raise ValueError("RAW_LOGS_BUCKET requis")

    import json

    vm_id = str(vm.get("vm_id") or vm.get("sk") or "unknown")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{prefix.rstrip('/')}/{vm_id}-{ts}.jsonl"
    body = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
    r = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    session = _aws_session(r)
    session.client("s3").put_object(
        Bucket=b,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return f"s3://{b}/{key}"
