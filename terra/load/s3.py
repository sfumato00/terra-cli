from __future__ import annotations

import json

import boto3

from terra.schema.state import State

_LOCK_SUFFIX = ".tflock"


def state_s3(
    bucket: str,
    key: str,
    profile: str | None = None,
    region: str | None = None,
) -> State:
    """Download and parse a Terraform state file from S3.

    Warns if a lock object exists alongside the state key (read-only — we never
    touch the lock).
    """
    session = boto3.Session(profile_name=profile, region_name=region)
    s3 = session.client("s3")

    _warn_if_locked(s3, bucket, key)

    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return State.model_validate(json.loads(body))


def _warn_if_locked(s3: object, bucket: str, key: str) -> None:
    import warnings

    lock_key = key + _LOCK_SUFFIX
    try:
        s3.head_object(Bucket=bucket, Key=lock_key)  # type: ignore[attr-defined]
        warnings.warn(
            f"Lock object detected at s3://{bucket}/{lock_key}. "
            "State may be in use — reading anyway (read-only).",
            stacklevel=3,
        )
    except Exception:
        pass
