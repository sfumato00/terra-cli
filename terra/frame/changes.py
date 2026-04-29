from __future__ import annotations

from typing import Any

import pandas as pd
import pyarrow as pa

from terra.schema.common import Action
from terra.schema.plan import Plan

_SCHEMA = pa.schema(
    [
        pa.field("address", pa.string()),
        pa.field("module_address", pa.string()),
        pa.field("type", pa.string()),
        pa.field("name", pa.string()),
        pa.field("provider", pa.string()),
        pa.field("mode", pa.string()),
        pa.field("actions", pa.list_(pa.string())),
        pa.field("action_reason", pa.string()),
        pa.field("attr_diff", pa.list_(pa.string())),
    ]
)


def changes_df(plan: Plan) -> pd.DataFrame:
    """Flatten plan.resource_changes into a typed DataFrame."""
    rows: list[dict] = []
    before_vals: list[dict] = []
    after_vals: list[dict] = []
    for rc in plan.resource_changes:
        before = rc.change.before or {}
        after = rc.change.after or {}
        attr_diff = _diff_keys(before, after)
        action_reason: str = getattr(rc.change, "action_reason", "") or ""
        rows.append(
            {
                "address": rc.address,
                "module_address": rc.module_address or "",
                "type": rc.type,
                "name": rc.name,
                "provider": rc.provider_name,
                "mode": rc.mode.value,
                "actions": [a.value for a in rc.change.actions],
                "action_reason": action_reason,
                "attr_diff": attr_diff,
            }
        )
        before_vals.append(before)
        after_vals.append(after)

    if not rows:
        return _empty()

    table = pa.Table.from_pylist(rows, schema=_SCHEMA)
    df = table.to_pandas()
    df["before"] = before_vals
    df["after"] = after_vals
    return df


def summary(plan: Plan) -> dict[str, int]:
    """Return {'add': N, 'change': N, 'destroy': N, 'no-op': N}."""
    counts: dict[str, int] = {"add": 0, "change": 0, "destroy": 0, "no-op": 0}
    for rc in plan.resource_changes:
        actions = rc.change.actions
        if Action.CREATE in actions and Action.DELETE not in actions:
            counts["add"] += 1
        elif Action.DELETE in actions and Action.CREATE not in actions:
            counts["destroy"] += 1
        elif Action.UPDATE in actions or (Action.CREATE in actions and Action.DELETE in actions):
            counts["change"] += 1
        else:
            counts["no-op"] += 1
    return counts


def _diff_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


def _empty() -> pd.DataFrame:
    return pa.schema(_SCHEMA).empty_table().to_pandas()
