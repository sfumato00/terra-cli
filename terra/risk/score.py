from __future__ import annotations

import pandas as pd

from .rules import apply_rules


def score(changes: pd.DataFrame) -> pd.DataFrame:
    """Add 'risk' and 'risk_reasons' columns to a changes DataFrame."""
    if changes.empty:
        df = changes.copy()
        df["risk"] = pd.Series(dtype="object")
        df["risk_reasons"] = pd.Series(dtype="object")
        return df

    risks: list[str] = []
    reasons: list[list[str]] = []
    for _, row in changes.iterrows():
        r, rs = apply_rules(row)
        risks.append(r)
        reasons.append(rs)

    df = changes.copy()
    df["risk"] = risks
    df["risk_reasons"] = reasons
    return df
