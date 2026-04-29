from __future__ import annotations

import base64
import difflib
import gzip
from typing import Any

import networkx as nx
import pandas as pd

from .rules import register
from .score import score

__all__ = ["score", "blast_radius", "user_data_diff", "register"]


def blast_radius(g: nx.DiGraph, address: str) -> set[str]:
    """Return the set of resources that depend (directly or transitively) on *address*.

    In terra's state graph, edges point from dependent → dependency (A → B means
    A depends on B). Resources that would be affected if *address* is destroyed are
    therefore the ancestors of *address* in that graph — the nodes that have *address*
    reachable via their outgoing dependency edges.
    """
    if address not in g:
        return set()
    return nx.ancestors(g, address)


def user_data_diff(changes: pd.DataFrame) -> list[dict[str, Any]]:
    """Decode and diff user_data / user_data_base64 for each instance change.

    Returns one dict per affected row with keys:
      address, field, before_text, after_text, unified_diff
    """
    results: list[dict[str, Any]] = []
    if changes.empty:
        return results

    for _, row in changes.iterrows():
        attr_diff = row.get("attr_diff") or []
        for field in ("user_data", "user_data_base64"):
            if field not in attr_diff:
                continue
            before_val = (row.get("before") or {}).get(field, "")
            after_val = (row.get("after") or {}).get(field, "")
            before_text = _decode_user_data(before_val or "")
            after_text = _decode_user_data(after_val or "")
            diff = list(
                difflib.unified_diff(
                    before_text.splitlines(keepends=True),
                    after_text.splitlines(keepends=True),
                    fromfile=f"{row['address']} (before)",
                    tofile=f"{row['address']} (after)",
                )
            )
            results.append(
                {
                    "address": row["address"],
                    "field": field,
                    "before_text": before_text,
                    "after_text": after_text,
                    "unified_diff": "".join(diff),
                }
            )
    return results


def _decode_user_data(value: str) -> str:
    """Decode base64 (and optionally gzip) user_data to a readable string."""
    if not value:
        return ""
    try:
        raw = base64.b64decode(value)
        try:
            return gzip.decompress(raw).decode("utf-8", errors="replace")
        except (OSError, gzip.BadGzipFile):
            return raw.decode("utf-8", errors="replace")
    except Exception:
        return value
