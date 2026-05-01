"""
SageMaker Endpoint Configuration Manager

Manage endpoint configuration files and environment variables.
"""

import json
import os
from pathlib import Path
from typing import Optional


class EndpointConfig:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self._config = None
        self._load_config()

    def _load_config(self):
        if self.config_path and Path(self.config_path).exists():
            with open(self.config_path) as f:
                self._config = json.load(f)
            return

        #common locations
        for path in [
            Path("endpoint_config.json"),
            Path(__file__).parent / "endpoint_config.json",
            Path.home() / ".sagemaker" / "endpoint_config.json",
        ]:
            if path.exists():
                with open(path) as f:
                    self._config = json.load(f)
                self.config_path = str(path)
                return

        #environment variable
        if "SAGEMAKER_ENDPOINT_CONFIG" in os.environ:
            self._config = json.loads(os.environ["SAGEMAKER_ENDPOINT_CONFIG"])
            return

        raise FileNotFoundError(
            "Could not find endpoint_config.json. "
            "Run upload_to_sagemaker.py first to generate it."
        )

    @property
    def endpoint_name(self) -> str:
        """Get endpoint name."""
        return self._config["endpoint_name"]

    @property
    def model_s3_uri(self) -> str:
        """Get model S3 URI."""
        return self._config["model_s3_uri"]

    @property
    def instance_type(self) -> str:
        """Get instance type."""
        return self._config.get("instance_type", "ml.m5.large")

    @property
    def created_at(self) -> str:
        """Get creation timestamp."""
        return self._config.get("created_at", "unknown")

    def to_dict(self) -> dict:
        """Get full configuration as dict."""
        return dict(self._config)

    def save(self, path: str):
        """Save configuration to file."""
        with open(path, "w") as f:
            json.dump(self._config, f, indent=2)

    def __repr__(self) -> str:
        return (
            f"EndpointConfig(endpoint_name='{self.endpoint_name}', "
            f"instance_type='{self.instance_type}')"
        )


def get_default_predictor():
    """Create SageMaker predictor with default config.
    Convenience function for quick endpoint calls.
    """
    from sagemaker_client import SageMakerPredictor

    config = EndpointConfig()
    return SageMakerPredictor(config.endpoint_name)
