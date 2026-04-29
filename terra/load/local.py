from __future__ import annotations

import json
import subprocess
from pathlib import Path

from terra.schema.plan import Plan
from terra.schema.state import State


def plan(path: str | Path) -> Plan:
    """Parse a compiled plan binary via `terraform show -json`."""
    result = subprocess.run(
        ["terraform", "show", "-json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return Plan.model_validate_json(result.stdout)


def plan_json(path: str | Path) -> Plan:
    """Parse a pre-exported plan JSON file directly (no terraform binary needed)."""
    return Plan.model_validate(json.loads(Path(path).read_text()))


def state_local(path: str | Path) -> State:
    """Parse a local terraform.tfstate file."""
    return State.model_validate(json.loads(Path(path).read_text()))
