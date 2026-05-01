"""
Unit tests for SageMaker Endpoint Client

Usage:
    pytest tests/test_sagemaker_client.py
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from sagemaker_client import SageMakerPredictor


@pytest.fixture
def mock_runtime_client():
    """Mock SageMaker runtime client."""
    return MagicMock()


@pytest.fixture
def predictor(mock_runtime_client):
    """Create predictor with mocked runtime client."""
    with patch(
        "backend.model.attack_predictor.sagemaker_client.boto3.client",
        return_value=mock_runtime_client,
    ):
        return SageMakerPredictor("test-endpoint")


class TestSageMakerPredictor:
    """Test SageMaker endpoint client."""

    def test_predict_single_event(self, predictor, mock_runtime_client):
        """Test predicting a single event."""
        # Mock response
        mock_response = {
            "Body": MagicMock(
                read=lambda: json.dumps({
                    "predictions": [
                        {
                            "predicted_attack_type": "ddos",
                            "probabilities": {
                                "ddos": 0.92,
                                "brute_force": 0.05,
                                "port_scan": 0.03,
                            },
                            "top_probability": 0.92,
                            "feature_dim": 128,
                        }
                    ]
                }).encode("utf-8")
            )
        }
        mock_runtime_client.invoke_endpoint.return_value = mock_response

        # Test
        event = {"source_ip": "192.168.1.1", "port": 443}
        result = predictor.predict(event)

        # Verify
        assert "predictions" in result
        assert result["predictions"][0]["predicted_attack_type"] == "ddos"
        assert result["predictions"][0]["probabilities"]["ddos"] == 0.92

        # Verify endpoint was called correctly
        call_args = mock_runtime_client.invoke_endpoint.call_args
        assert call_args.kwargs["EndpointName"] == "test-endpoint"
        assert call_args.kwargs["ContentType"] == "application/json"

        body = json.loads(call_args.kwargs["Body"])
        assert "event" in body
        assert body["event"]["source_ip"] == "192.168.1.1"

    def test_predict_batch(self, predictor, mock_runtime_client):
        """Test predicting multiple events."""
        # Mock response
        mock_response = {
            "Body": MagicMock(
                read=lambda: json.dumps({
                    "predictions": [
                        {
                            "predicted_attack_type": "ddos",
                            "probabilities": {"ddos": 0.92, "brute_force": 0.05, "port_scan": 0.03},
                        },
                        {
                            "predicted_attack_type": "port_scan",
                            "probabilities": {"ddos": 0.1, "brute_force": 0.2, "port_scan": 0.7},
                        },
                    ]
                }).encode("utf-8")
            )
        }
        mock_runtime_client.invoke_endpoint.return_value = mock_response

        # Test
        events = [
            {"source_ip": "192.168.1.1", "port": 443},
            {"source_ip": "192.168.1.2", "port": 22},
        ]
        result = predictor.predict_batch(events)

        # Verify
        assert len(result["predictions"]) == 2
        assert result["predictions"][0]["predicted_attack_type"] == "ddos"
        assert result["predictions"][1]["predicted_attack_type"] == "port_scan"

        # Verify batch payload
        call_args = mock_runtime_client.invoke_endpoint.call_args
        body = json.loads(call_args.kwargs["Body"])
        assert "instances" in body
        assert len(body["instances"]) == 2

    def test_get_predicted_attack_type(self, predictor, mock_runtime_client):
        """Test convenience method for getting attack type."""
        mock_response = {
            "Body": MagicMock(
                read=lambda: json.dumps({
                    "predictions": [
                        {
                            "predicted_attack_type": "brute_force",
                            "probabilities": {},
                        }
                    ]
                }).encode("utf-8")
            )
        }
        mock_runtime_client.invoke_endpoint.return_value = mock_response

        event = {"source_ip": "192.168.1.1"}
        attack_type = predictor.get_predicted_attack_type(event)

        assert attack_type == "brute_force"

    def test_get_probabilities(self, predictor, mock_runtime_client):
        """Test convenience method for getting probabilities."""
        probs = {
            "ddos": 0.5,
            "brute_force": 0.3,
            "port_scan": 0.2,
        }
        mock_response = {
            "Body": MagicMock(
                read=lambda: json.dumps({
                    "predictions": [
                        {
                            "predicted_attack_type": "ddos",
                            "probabilities": probs,
                        }
                    ]
                }).encode("utf-8")
            )
        }
        mock_runtime_client.invoke_endpoint.return_value = mock_response

        event = {"source_ip": "192.168.1.1"}
        result_probs = predictor.get_probabilities(event)

        assert result_probs == probs

    def test_invalid_response_returns_unknown(self, predictor, mock_runtime_client):
        """Test that invalid responses return sensible defaults."""
        mock_response = {
            "Body": MagicMock(
                read=lambda: json.dumps({
                    "predictions": []
                }).encode("utf-8")
            )
        }
        mock_runtime_client.invoke_endpoint.return_value = mock_response

        event = {"source_ip": "192.168.1.1"}
        attack_type = predictor.get_predicted_attack_type(event)

        assert attack_type == "unknown"


# Integration test (requires real endpoint)
@pytest.mark.integration
def test_real_endpoint_predict():
    """Test predicting with real endpoint (requires running endpoint)."""
    # This test requires:
    # 1. Real AWS credentials
    # 2. Running SageMaker endpoint
    # 3. SAGEMAKER_ENDPOINT environment variable set

    import os

    endpoint = os.getenv("SAGEMAKER_ENDPOINT")
    if not endpoint:
        pytest.skip("SAGEMAKER_ENDPOINT not set")

    predictor = SageMakerPredictor(endpoint)

    event = {
        "source_ip": "192.168.1.1",
        "port": 443,
        "flags": "S",
        "payload_size": 100,
        "request_id": "abc123",
        # Add other required fields
    }

    result = predictor.predict(event)

    assert "predictions" in result
    assert len(result["predictions"]) > 0
    assert "predicted_attack_type" in result["predictions"][0]
    assert "probabilities" in result["predictions"][0]
