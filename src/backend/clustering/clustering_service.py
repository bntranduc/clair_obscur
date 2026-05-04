"""DBSCAN + arêtes k-voisins intra-cluster pour un graphe exploitable côté UI."""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.clustering.compact import compact_alert_for_clustering
from backend.clustering.features import build_feature_matrix

try:
    from sklearn.cluster import DBSCAN
    from sklearn.metrics.pairwise import euclidean_distances
    from sklearn.preprocessing import StandardScaler
except ImportError as e:  # pragma: no cover
    _IMPORT_ERR = e
    DBSCAN = None  # type: ignore[misc, assignment]
    StandardScaler = None  # type: ignore[misc, assignment]
    euclidean_distances = None  # type: ignore[misc, assignment]
else:
    _IMPORT_ERR = None


def _truncate(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _edges_within_clusters(
    X_scaled: np.ndarray,
    labels: np.ndarray,
    ids: list[str],
    max_neighbors: int,
) -> list[dict[str, Any]]:
    """Pour chaque cluster, relie chaque point à ses ``max_neighbors`` plus proches voisins dans le même cluster."""
    n = X_scaled.shape[0]
    if n < 2:
        return []

    dist = euclidean_distances(X_scaled)
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for c in np.unique(labels):
        if c < 0:
            continue
        idx = np.where(labels == c)[0]
        if len(idx) < 2:
            continue
        k_use = min(max(1, max_neighbors), len(idx) - 1)
        for i in idx:
            drow = dist[i, idx]
            order = np.argsort(drow)[1 : k_use + 1]
            for j_local in order:
                j = int(idx[j_local])
                a, b = ids[i], ids[j]
                if a == b:
                    continue
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                w = float(1.0 / (1e-6 + dist[i, j]))
                edges.append({"source": a, "target": b, "weight": round(w, 6)})

    return edges


def compute_alert_cluster_graph(
    alerts_raw: list[dict[str, Any]],
    *,
    eps: float = 1.05,
    min_samples: int = 2,
    max_neighbors: int = 3,
) -> dict[str, Any]:
    """
    Compacte les alertes, calcule les traits, DBSCAN sur données standardisées,
    produit nœuds + liens pour visualisation graphe.

    Lève ``RuntimeError`` si scikit-learn / numpy ne sont pas disponibles.
    """
    if _IMPORT_ERR is not None:
        raise RuntimeError(
            "scikit-learn est requis pour le clustering (pip install scikit-learn numpy)."
        ) from _IMPORT_ERR

    alerts_raw = [a for a in alerts_raw if isinstance(a, dict)]
    alerts = [compact_alert_for_clustering(a) for a in alerts_raw]
    n = len(alerts)
    if n == 0:
        return {
            "nodes": [],
            "edges": [],
            "clusters": [],
            "meta": {
                "count": 0,
                "algorithm": "dbscan",
                "eps": eps,
                "min_samples": min_samples,
                "noise_count": 0,
                "feature_columns": [
                    "severity_rank",
                    "time_norm",
                    "attack_category_norm",
                    "ip_o1",
                    "ip_o2",
                    "ip_o3",
                    "ip_o4",
                    "victim_count_norm",
                ],
            },
        }

    X, ids, _finite_ts = build_feature_matrix(alerts)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    clusterer = DBSCAN(eps=eps, min_samples=min_samples)
    labels = clusterer.fit_predict(Xs)

    nodes: list[dict[str, Any]] = []
    for i, aid in enumerate(ids):
        lbl = int(labels[i])
        ra = alerts_raw[i] if i < len(alerts_raw) else {}
        det = ra.get("detection") if isinstance(ra.get("detection"), dict) else {}
        atk = (
            str(det.get("attack_type", "")).strip()
            or str(ra.get("challenge_id", "")).strip()
            or "—"
        )
        nodes.append(
            {
                "id": aid,
                "label": atk,
                "cluster_id": lbl,
                "severity": str(ra.get("severity", "") or ""),
                "title": _truncate(str(ra.get("alert_summary", "") or ""), 120),
            }
        )

    edges = _edges_within_clusters(Xs, labels, ids, max_neighbors=max_neighbors)

    uniq_labels = [int(x) for x in sorted(set(labels.tolist()))]
    clusters_meta: list[dict[str, Any]] = []
    for c in uniq_labels:
        count = int(np.sum(labels == c))
        clusters_meta.append(
            {
                "id": c,
                "label": "Bruit" if c < 0 else f"Cluster {c}",
                "size": count,
            }
        )

    noise_count = int(np.sum(labels < 0))

    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters_meta,
        "meta": {
            "count": n,
            "algorithm": "dbscan",
            "eps": eps,
            "min_samples": min_samples,
            "max_neighbors": max_neighbors,
            "noise_count": noise_count,
            "n_clusters": len([c for c in uniq_labels if c >= 0]),
            "feature_columns": [
                "severity_rank",
                "time_norm",
                "attack_category_norm",
                "ip_o1",
                "ip_o2",
                "ip_o3",
                "ip_o4",
                "victim_count_norm",
            ],
        },
    }
