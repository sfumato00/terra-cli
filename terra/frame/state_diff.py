from __future__ import annotations

from typing import Any

import pandas as pd
import pyarrow as pa

from terra.schema.state import State

from ._flatten import walk_modules

_SCHEMA = pa.schema(
    [
        pa.field("address", pa.string()),
        pa.field("diff_type", pa.string()),  # "added" | "removed" | "changed"
        pa.field("changed_attrs", pa.list_(pa.string())),
    ]
)


def state_diff(before: State, after: State) -> pd.DataFrame:
    """Compare two State objects; return a DataFrame of added/removed/changed resources."""
    before_map = _resource_map(before)
    after_map = _resource_map(after)

    rows: list[dict[str, Any]] = []

    for addr in sorted(set(before_map) | set(after_map)):
        if addr not in before_map:
            rows.append({"address": addr, "diff_type": "added", "changed_attrs": []})
        elif addr not in after_map:
            rows.append({"address": addr, "diff_type": "removed", "changed_attrs": []})
        else:
            bv = before_map[addr]
            av = after_map[addr]
            changed = sorted(k for k in set(bv) | set(av) if bv.get(k) != av.get(k))
            if changed:
                rows.append({"address": addr, "diff_type": "changed", "changed_attrs": changed})

    if not rows:
        return pa.schema(_SCHEMA).empty_table().to_pandas()

    return pa.Table.from_pylist(rows, schema=_SCHEMA).to_pandas()


def _resource_map(state: State) -> dict[str, dict[str, Any]]:
    if state.values is None:
        return {}
    return {
        resource.address: resource.values
        for _, resource in walk_modules(state.values.root_module)
    }
