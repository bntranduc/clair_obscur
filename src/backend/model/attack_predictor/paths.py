"""Chemins par défaut pour les artefacts du classificateur."""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent

# Dossier de sauvegarde local (joblibs + metadata + metrics)
DEFAULT_LOCAL_MODEL_DIR = _PACKAGE_DIR / "predictors"
