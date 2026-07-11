"""Enregistrement VM, approbation admin, envoi de logs via l'API."""

from __future__ import annotations

import json
import os
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.aws.dynamodb_vms import (
    approve_vm,
    create_s3_prefix_marker,
    get_vm_by_token,
    list_all_vms,
    register_vm,
    reject_vm,
    revoke_vm,
    ship_events_to_s3,
    touch_last_ship,
)

router = APIRouter(prefix="/api/v1/vms", tags=["vms"])


class VmRegisterRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=256)
    fingerprint: str = Field(default="", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VmShipRequest(BaseModel):
    events: list[dict[str, Any]] = Field(..., min_length=1, max_length=5000)


def _extract_bearer(authorization: str | None) -> str:
    raw = (authorization or "").strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw


async def require_vm_token(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Token VM requis (Authorization: Bearer …)")
    try:
        vm = get_vm_by_token(token)
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if vm is None:
        raise HTTPException(status_code=401, detail="Token VM invalide")
    return vm


@router.post("/register")
def post_register_vm(req: VmRegisterRequest) -> dict[str, Any]:
    """Enregistre une VM en attente d'approbation. Retourne un token à conserver localement."""
    try:
        vm = register_vm(
            hostname=req.hostname.strip(),
            fingerprint=req.fingerprint.strip(),
            metadata=req.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {
        "vm_id": vm["vm_id"],
        "status": vm["status"],
        "api_token": vm["api_token"],
        "message": "En attente d'approbation par l'administrateur.",
    }


@router.get("/me")
def get_vm_me(vm: dict[str, Any] = Depends(require_vm_token)) -> dict[str, Any]:
    """Statut de la VM connectée (polling depuis connect.sh)."""
    return {
        "vm_id": vm.get("vm_id"),
        "hostname": vm.get("hostname"),
        "status": vm.get("status"),
        "s3_prefix": vm.get("s3_prefix"),
        "registered_at": vm.get("registered_at"),
        "approved_at": vm.get("approved_at"),
        "last_ship_at": vm.get("last_ship_at"),
    }


@router.post("/ship")
def post_vm_ship(
    req: VmShipRequest,
    vm: dict[str, Any] = Depends(require_vm_token),
) -> dict[str, Any]:
    """Reçoit des événements normalisés et les écrit dans le préfixe S3 de la VM."""
    if vm.get("status") != "approved":
        raise HTTPException(
            status_code=403,
            detail=f"VM non approuvée (statut: {vm.get('status')}).",
        )
    try:
        uri = ship_events_to_s3(vm, req.events)
        touch_last_ship(str(vm.get("vm_id") or ""))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except (ClientError, BotoCoreError, ValueError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True, "shipped": len(req.events), "s3_uri": uri}


@router.get("")
def get_vms_list() -> dict[str, Any]:
    """Liste toutes les VMs (admin dashboard)."""
    try:
        vms = list_all_vms()
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"vms": vms, "count": len(vms)}


@router.post("/{vm_id}/approve")
def post_approve_vm(vm_id: str) -> dict[str, Any]:
    """Approuve une VM : crée le préfixe S3 et autorise l'envoi de logs."""
    try:
        vm = approve_vm(vm_id)
        marker = create_s3_prefix_marker(vm_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ClientError, BotoCoreError, ValueError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True, "vm": vm, "s3_marker": marker}


@router.post("/{vm_id}/reject")
def post_reject_vm(vm_id: str) -> dict[str, Any]:
    try:
        vm = reject_vm(vm_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True, "vm": vm}


@router.delete("/{vm_id}")
def delete_vm(vm_id: str) -> dict[str, Any]:
    """Révoque une VM (plus d'envoi autorisé)."""
    try:
        vm = revoke_vm(vm_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True, "vm": vm}
