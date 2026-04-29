from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd

Risk = str  # "high" | "low" | "none"
Rule = Callable[[pd.Series], tuple[str, str] | None]

_STATEFUL_TYPES = {
    "aws_rds_cluster",
    "aws_rds_instance",
    "aws_db_instance",
    "aws_ebs_volume",
    "aws_s3_bucket",
    "aws_dynamodb_table",
    "aws_elasticache_cluster",
    "aws_elasticache_replication_group",
    "google_sql_database_instance",
    "azurerm_sql_server",
}

_IAM_POLICY_TYPES = {
    "aws_iam_policy",
    "aws_iam_role_policy",
    "aws_iam_user_policy",
    "aws_iam_group_policy",
}

_INSTANCE_TYPES = {
    "aws_instance",
    "aws_launch_template",
    "aws_launch_configuration",
    "google_compute_instance",
    "azurerm_virtual_machine",
}

_SEVERITY_ORDER: dict[str, int] = {"high": 2, "low": 1, "none": 0}


def _attr_diff(row: pd.Series) -> list[str]:
    """Safely extract attr_diff as a Python list (handles numpy arrays)."""
    val = row.get("attr_diff")
    if val is None:
        return []
    try:
        return list(val)
    except (TypeError, ValueError):
        return []


def _contains_wildcard(obj: Any) -> bool:
    """Return True if the string '*' appears as a value anywhere in obj."""
    if obj == "*":
        return True
    if isinstance(obj, dict):
        return any(_contains_wildcard(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_wildcard(item) for item in obj)
    if isinstance(obj, str) and (obj.startswith("{") or obj.startswith("[")):
        try:
            return _contains_wildcard(json.loads(obj))
        except (json.JSONDecodeError, ValueError):
            pass
    return False


def stateful_delete(row: pd.Series) -> tuple[str, str] | None:
    if row["type"] in _STATEFUL_TYPES and "delete" in row["actions"]:
        return "high", f"deleting stateful resource {row['type']}"
    return None


def replace_no_cbd(row: pd.Series) -> tuple[str, str] | None:
    actions = list(row["actions"])
    if "delete" in actions and "create" in actions and actions[0] == "delete":
        return "high", "destroy-before-create replace (missing create_before_destroy)"
    return None


def iam_widening(row: pd.Series) -> tuple[str, str] | None:
    if row["type"] not in _IAM_POLICY_TYPES:
        return None
    before = row.get("before") or {}
    after = row.get("after") or {}
    if _contains_wildcard(after) and not _contains_wildcard(before):
        return "high", "IAM policy change introduces wildcard (*) action or resource"
    return None


def user_data_mutation(row: pd.Series) -> tuple[str, str] | None:
    if row["type"] not in _INSTANCE_TYPES:
        return None
    diff = _attr_diff(row)
    if any(a in diff for a in ("user_data", "user_data_base64")):
        return "high", "user_data change forces instance replacement (reprovision)"
    return None


def tag_only_update(row: pd.Series) -> tuple[str, str] | None:
    if list(row["actions"]) != ["update"]:
        return None
    diff = _attr_diff(row)
    if diff and all("tag" in k.lower() for k in diff):
        return "low", "tag-only update (no functional change)"
    return None


_RULES: list[Rule] = [
    stateful_delete,
    replace_no_cbd,
    iam_widening,
    user_data_mutation,
    tag_only_update,
]


def register(rule: Rule) -> Rule:
    """Register a custom rule. Returns the rule unchanged (usable as a decorator)."""
    _RULES.append(rule)
    return rule


def apply_rules(row: pd.Series) -> tuple[str, list[str]]:
    """Return (highest_risk_level, [all_reasons]) for one changes row."""
    results: list[tuple[str, str]] = []
    for rule in _RULES:
        result = rule(row)
        if result is not None:
            results.append(result)
    if not results:
        return "none", []
    results.sort(key=lambda r: _SEVERITY_ORDER.get(r[0], 0), reverse=True)
    return results[0][0], [r[1] for r in results]
