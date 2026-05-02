"""Clients S3 légers."""

from backend.aws.s3.logs import fetch_all_normalized_logs

__all__ = [
    "fetch_all_alerts_from_s3",
    "fetch_all_normalized_logs",
    "print_all_alerts_from_s3",
]


def __getattr__(name: str):
    if name == "fetch_all_alerts_from_s3":
        from backend.aws.s3.alerts import fetch_all_alerts_from_s3

        return fetch_all_alerts_from_s3
    if name == "print_all_alerts_from_s3":
        from backend.aws.s3.alerts import print_all_alerts_from_s3

        return print_all_alerts_from_s3
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
