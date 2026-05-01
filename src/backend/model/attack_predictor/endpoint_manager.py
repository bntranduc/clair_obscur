"""
SageMaker Endpoint Management Utilities
"""

import json
from datetime import datetime
from typing import Optional
import boto3


class EndpointManager:
    """Manage SageMaker endpoint lifecycle."""

    def __init__(self, endpoint_name: str, region_name: str = "us-east-1"):
        """Initialize endpoint manager.
        
        Args:
            endpoint_name: Name of the SageMaker endpoint
            region_name: AWS region
        """
        self.endpoint_name = endpoint_name
        self.sagemaker_client = boto3.client("sagemaker", region_name=region_name)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=region_name)

    def get_status(self) -> str:
        """Get endpoint status (Creating, InService, Updating, Deleting, Failed)."""
        response = self.sagemaker_client.describe_endpoint(EndpointName=self.endpoint_name)
        return response["EndpointStatus"]

    def get_details(self) -> dict:
        """Get full endpoint details."""
        response = self.sagemaker_client.describe_endpoint(EndpointName=self.endpoint_name)
        return {
            "endpoint_name": response["EndpointName"],
            "status": response["EndpointStatus"],
            "creation_time": str(response.get("CreationTime", "")),
            "last_modified_time": str(response.get("LastModifiedTime", "")),
            "instance_type": response.get("EndpointConfigName", ""),
            "variant_weights": response.get("EndpointConfigName", ""),
            "url": response.get("EndpointArn", ""),
        }

    def is_ready(self) -> bool:
        """Check if endpoint is ready (InService status)."""
        return self.get_status() == "InService"

    def wait_until_ready(self, max_wait_seconds: int = 3600) -> bool:
        """Wait until endpoint is ready.
        
        Args:
            max_wait_seconds: Maximum seconds to wait (default: 1 hour)
            
        Returns:
            True if ready, False if timeout
        """
        import time

        start = time.time()
        while time.time() - start < max_wait_seconds:
            if self.is_ready():
                return True
            print(f"Waiting for endpoint... Status: {self.get_status()}")
            time.sleep(30)

        return False

    def get_metrics(
        self,
        metric_name: str = "ModelLatency",
        period: int = 300,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[dict]:
        """Get CloudWatch metrics for endpoint.
        
        Common metrics:
            - ModelLatency (milliseconds)
            - Invocations (count)
            - ModelSetupTime (milliseconds)
            - Errors (count)
        
        Args:
            metric_name: CloudWatch metric name
            period: Period in seconds
            start_time: Start time (default: 1 hour ago)
            end_time: End time (default: now)
            
        Returns:
            List of metric datapoints
        """
        from datetime import timedelta

        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(hours=1)

        response = self.cloudwatch_client.get_metric_statistics(
            Namespace="AWS/SageMaker",
            MetricName=metric_name,
            Dimensions=[
                {"Name": "EndpointName", "Value": self.endpoint_name},
                {"Name": "VariantName", "Value": "AllTraffic"},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=["Average", "Maximum", "Minimum", "Sum"],
        )

        return response.get("Datapoints", [])

    def get_invocation_count(self, hours: int = 1) -> int:
        """Get total invocations in last N hours."""
        from datetime import timedelta

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        datapoints = self.get_metrics(
            metric_name="Invocations",
            period=3600,
            start_time=start_time,
            end_time=end_time,
        )

        return sum(int(dp.get("Sum", 0)) for dp in datapoints)

    def get_average_latency(self, hours: int = 1) -> float:
        """Get average model latency in last N hours (in milliseconds)."""
        from datetime import timedelta

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        datapoints = self.get_metrics(
            metric_name="ModelLatency",
            period=3600,
            start_time=start_time,
            end_time=end_time,
        )

        if not datapoints:
            return 0.0

        avg_sum = sum(dp.get("Average", 0) for dp in datapoints)
        return avg_sum / len(datapoints)

    def scale(self, instance_count: int) -> None:
        """Scale endpoint to new instance count.
        
        Args:
            instance_count: Number of instances
        """
        # Get current endpoint config
        endpoint = self.sagemaker_client.describe_endpoint(EndpointName=self.endpoint_name)
        variant_name = endpoint["ProductionVariants"][0]["VariantName"]

        # Update variant
        self.sagemaker_client.update_endpoint_weights_and_capacities(
            EndpointName=self.endpoint_name,
            DesiredWeightsAndCapacities=[
                {
                    "VariantName": variant_name,
                    "DesiredInstanceCount": instance_count,
                }
            ],
        )

        print(f"Scaling endpoint to {instance_count} instances...")

    def delete(self, confirm: bool = False) -> None:
        """Delete endpoint and config.
        
        Args:
            confirm: Require confirmation before deleting
        """
        if confirm:
            response = input(f"Delete endpoint {self.endpoint_name}? (yes/no): ")
            if response.lower() != "yes":
                print("Cancelled")
                return

        print(f"Deleting endpoint {self.endpoint_name}...")
        self.sagemaker_client.delete_endpoint(EndpointName=self.endpoint_name)
        print("✓ Endpoint deleted")

    def describe(self) -> None:
        """Print endpoint details and metrics."""
        details = self.get_details()
        status = self.get_status()

        print(f"\n{'='*60}")
        print(f"ENDPOINT: {self.endpoint_name}")
        print(f"{'='*60}")
        print(f"Status:            {status}")
        print(f"Created:           {details['creation_time']}")
        print(f"Last Modified:     {details['last_modified_time']}")
        print(f"Instance Type:     {details['instance_type']}")

        if status == "InService":
            try:
                invocations = self.get_invocation_count(hours=1)
                latency = self.get_average_latency(hours=1)
                print(f"\nMetrics (last hour):")
                print(f"  Invocations:     {invocations}")
                print(f"  Avg Latency:     {latency:.2f} ms")
            except Exception as e:
                print(f"  Could not fetch metrics: {e}")

        print(f"{'='*60}\n")


# CLI tool
def main():
    """Command-line endpoint manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage SageMaker endpoints")
    parser.add_argument("endpoint_name", help="Endpoint name")
    parser.add_argument("--status", action="store_true", help="Get endpoint status")
    parser.add_argument("--describe", action="store_true", help="Get full details")
    parser.add_argument("--wait", action="store_true", help="Wait until ready")
    parser.add_argument("--metrics", action="store_true", help="Get metrics")
    parser.add_argument("--scale", type=int, help="Scale to N instances")
    parser.add_argument("--region", default="us-east-1", help="AWS region")

    args = parser.parse_args()

    manager = EndpointManager(args.endpoint_name, region_name=args.region)

    try:
        if args.status:
            print(f"Status: {manager.get_status()}")
        elif args.describe:
            manager.describe()
        elif args.wait:
            print("Waiting for endpoint to be ready...")
            if manager.wait_until_ready():
                print("✓ Endpoint is ready!")
            else:
                print("✗ Timeout waiting for endpoint")
        elif args.metrics:
            manager.describe()
        elif args.scale:
            manager.scale(args.scale)
        else:
            manager.describe()

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
