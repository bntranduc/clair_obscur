"""
Clustering d'alertes SOC : vecteurs de traits sur un sous-ensemble de champs,
DBSCAN sur données standardisées, graphe k-voisins intra-cluster pour visualisation.

Entrée attendue par alerte (champs utilisés si présents) :
- ``id``, ``challenge_id``, ``severity``
- ``detection.attack_type``, ``detection.attack_start_time``, ``detection.attacker_ips``, ``detection.victim_accounts``
"""

from backend.clustering.clustering_service import compute_alert_cluster_graph

__all__ = ["compute_alert_cluster_graph"]
