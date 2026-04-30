from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from terra.frame import resources_df
from terra.load import state_cached, state_from_parquet, state_local, state_to_parquet
from terra.schema.state import State

FIXTURES = Path(__file__).parent / "fixtures"


def test_state_to_parquet_round_trip(tmp_path: Path, state: State) -> None:
    cache = tmp_path / "state.parquet"
    state_to_parquet(state, cache)

    assert cache.exists()
    reloaded = state_from_parquet(cache)

    # Pydantic equality covers structural identity.
    assert reloaded == state
    # And the derived DataFrame round-trips identically.
    assert resources_df(reloaded).equals(resources_df(state))


def test_state_cached_miss_writes_cache(tmp_path: Path) -> None:
    src = tmp_path / "state.json"
    shutil.copy(FIXTURES / "state.json", src)
    cache = tmp_path / "state.parquet"

    assert not cache.exists()
    state = state_cached(src, cache)
    assert cache.exists()
    assert state == state_local(src)


def test_state_cached_hit_skips_reparse(tmp_path: Path) -> None:
    src = tmp_path / "state.json"
    shutil.copy(FIXTURES / "state.json", src)
    cache = tmp_path / "state.parquet"

    # Prime the cache.
    state_cached(src, cache)
    cache_mtime = cache.stat().st_mtime

    # Make cache strictly fresher than source so the hit path fires.
    os.utime(cache, (cache_mtime + 10, cache_mtime + 10))

    # Corrupt the source — a hit must NOT re-read it.
    src.write_text("{not valid json")
    state = state_cached(src, cache)
    assert state.format_version == "4"  # fixture value preserved


def test_state_cached_stale_reparses(tmp_path: Path) -> None:
    src = tmp_path / "state.json"
    shutil.copy(FIXTURES / "state.json", src)
    cache = tmp_path / "state.parquet"

    state_cached(src, cache)
    # Make source strictly newer than cache.
    cache_mtime = cache.stat().st_mtime
    os.utime(src, (cache_mtime + 10, cache_mtime + 10))

    # Corrupt source so a re-parse raises — proves we hit the miss path.
    src.write_text("{not valid json")
    with pytest.raises(json.JSONDecodeError):
        state_cached(src, cache)
