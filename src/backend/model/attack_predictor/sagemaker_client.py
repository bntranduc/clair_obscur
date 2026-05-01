"""
SageMaker Endpoint Client

Call deployed prediction model endpoint from Python API.

Usage:
    client = SageMakerPredictor("my-endpoint")
    
    # Single event
    result = client.predict(event={"field1": "value", ...})
    
    # Batch
    result = client.predict_batch([
        {"field1": "value", ...},
        {"field1": "value", ...}
    ])
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import boto3


class SageMakerPredictor:
    """Call a SageMaker attack predictor endpoint."""

    def __init__(self, endpoint_name: str, region_name: str = "us-east-1"):
        """Initialize SageMaker runtime client.
        
        Args:
            endpoint_name: Name of the SageMaker endpoint
            region_name: AWS region (default: us-east-1)
        """
        self.endpoint_name = endpoint_name
        self.runtime_client = boto3.client("sagemaker-runtime", region_name=region_name)

    def predict(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Predict for a single event.
        
        Args:
            event: Normalized event dict
            
        Returns:
            Response dict with 'predictions' list containing:
                - predicted_attack_type: str
                - probabilities: dict[str, float]
                - top_probability: float
                - feature_dim: int
        """
        payload = {"event": dict(event)}
        return self._invoke_endpoint(payload)

    def predict_batch(self, events: list[Mapping[str, Any]]) -> dict[str, Any]:
        """Predict for multiple events.
        
        Args:
            events: List of normalized event dicts
            
        Returns:
            Response dict with 'predictions' list (one per event)
        """
        instances = [{"event": dict(e)} for e in events]
        payload = {"instances": instances}
        return self._invoke_endpoint(payload)

    def _invoke_endpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke endpoint with payload and return response."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        
        response = self.runtime_client.invoke_endpoint(
            EndpointName=self.endpoint_name,
            ContentType="application/json",
            Body=body,
        )
        
        result_body = response["Body"].read().decode("utf-8")
        return json.loads(result_body)

    def get_probabilities(self, event: Mapping[str, Any]) -> dict[str, float]:
        """Get attack type probabilities for a single event.
        
        Convenience method that extracts just the probabilities.
        """
        result = self.predict(event)
        predictions = result.get("predictions", [])
        if predictions:
            return predictions[0].get("probabilities", {})
        return {}

    def get_predicted_attack_type(self, event: Mapping[str, Any]) -> str:
        """Get predicted attack type for a single event.
        
        Convenience method that extracts just the label.
        """
        result = self.predict(event)
        predictions = result.get("predictions", [])
        if predictions:
            return predictions[0].get("predicted_attack_type", "unknown")
        return "unknown"


# Example usage from Flask/Chalice API
def example_api_usage():
    """Example: call endpoint from FastAPI/Chalice endpoint."""
    from backend.log.normalization.normalize import normalize_raw_log
    
    # Initialize client (load endpoint name from config)
    client = SageMakerPredictor("attack-predictor-endpoint")
    
    # Simulate receiving raw log
    raw_log = {"source_ip": "192.168.1.1", "port": 443, "flags": "S", ...}
    normalized_event = normalize_raw_log(raw_log)
    
    # Get prediction
    result = client.predict(normalized_event)
    attack_type = result["predictions"][0]["predicted_attack_type"]
    probs = result["predictions"][0]["probabilities"]
    
    return {"attack_type": attack_type, "probabilities": probs}
