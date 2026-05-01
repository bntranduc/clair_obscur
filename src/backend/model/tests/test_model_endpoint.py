from __future__ import annotations

from fastapi.testclient import TestClient

from backend.model.serve_app import app, llm_item_to_ground_truth_hit, predictions_to_alerts


def test_health() -> None:
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_llm_item_to_ground_truth_hit_shape() -> None:
    row = {
        "challenge_id": "ssh_brute_force",
        "detection": {
            "attack_type": "ssh_brute_force",
            "attacker_ips": ["1.2.3.4"],
            "victim_accounts": ["u1"],
            "attack_start_time": "2026-01-01T00:00:00Z",
            "attack_end_time": "2026-01-01T01:00:00Z",
            "indicators": {"k": 1},
        },
        "detection_time_seconds": 300,
    }
    hit = llm_item_to_ground_truth_hit(row)
    assert hit["_index"] == "ground-truth-ds1"
    assert hit["_source"]["attack_type"] == "ssh_brute_force"
    assert hit["_source"]["attack_window"]["start"] == "2026-01-01T00:00:00Z"


def test_predictions_to_alerts_filters_non_dict() -> None:
    assert predictions_to_alerts([]) == []
    assert predictions_to_alerts([{"no": "detection"}]) == []


def test_predict_empty_events_validation() -> None:
    c = TestClient(app)
    r = c.post("/predict", json={"events": []})
    assert r.status_code == 422
