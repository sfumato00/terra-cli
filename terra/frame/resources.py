from __future__ import annotations

import pandas as pd
import pyarrow as pa

from terra.schema.state import State

from ._flatten import walk_modules

_SCHEMA = pa.schema(
    [
        pa.field("address", pa.string()),
        pa.field("module", pa.string()),
        pa.field("type", pa.string()),
        pa.field("name", pa.string()),
        pa.field("provider", pa.string()),
        pa.field("mode", pa.string()),
        pa.field("schema_version", pa.int64()),
        pa.field("dependencies", pa.list_(pa.string())),
    ]
)


def resources_df(state: State) -> pd.DataFrame:
    """Flatten all resources in a State into a typed DataFrame (one row per resource)."""
    if state.values is None:
        return _empty()

    rows: list[dict] = []
    for module_addr, res in walk_modules(state.values.root_module):
        rows.append(
            {
                "address": res.address,
                "module": module_addr,
                "type": res.type,
                "name": res.name,
                "provider": res.provider_name,
                "mode": res.mode.value,
                "schema_version": res.schema_version,
                "dependencies": res.dependencies,
            }
        )

    if not rows:
        return _empty()

    table = pa.Table.from_pylist(rows, schema=_SCHEMA)
    return table.to_pandas()


def _empty() -> pd.DataFrame:
    return pa.schema(_SCHEMA).empty_table().to_pandas()
