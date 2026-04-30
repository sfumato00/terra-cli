"""Parquet cache for parsed State.

State JSON parsing is the slowest step in the pipeline for large state files.
We round-trip the *raw* state JSON through a single-row Parquet table — Pydantic
parsing still happens on read, but the cache lets the auto-loader skip re-parsing
when the cache is fresher than the source file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from terra.schema.state import State

_RAW_JSON_COL = "raw_json"


def state_to_parquet(state: State, path: str | Path) -> None:
    """Serialize a State to a single-row Parquet file via PyArrow."""
    payload = state.model_dump_json(exclude_none=True)
    table = pa.table({_RAW_JSON_COL: [payload]})
    pq.write_table(table, str(path))  # type: ignore[no-untyped-call]


def state_from_parquet(path: str | Path) -> State:
    """Parse a State back out of a Parquet cache file."""
    table = pq.read_table(str(path), columns=[_RAW_JSON_COL])  # type: ignore[no-untyped-call]
    payload = table.column(_RAW_JSON_COL)[0].as_py()
    return State.model_validate(json.loads(payload))


def state_cached(source: str | Path, cache: str | Path) -> State:
    """Load a State, using `cache` if it is fresher than `source`.

    On a cache miss (cache absent or stale), parses `source` JSON, writes the
    cache, and returns the parsed State.
    """
    source_path = Path(source)
    cache_path = Path(cache)

    if cache_path.exists() and cache_path.stat().st_mtime >= source_path.stat().st_mtime:
        return state_from_parquet(cache_path)

    state = State.model_validate(json.loads(source_path.read_text()))
    state_to_parquet(state, cache_path)
    return state
