"""Stockage des alertes SOC (jeu de données local ou futur backend)."""

from backend.alerts.store import alerts_json_path, load_all_alerts

__all__ = ["alerts_json_path", "load_all_alerts"]
