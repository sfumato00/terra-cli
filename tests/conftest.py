from pathlib import Path

import pytest

from terra.load.local import plan_json, state_local
from terra.schema.plan import Plan
from terra.schema.state import State

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def state() -> State:
    return state_local(FIXTURES / "state.json")


@pytest.fixture()
def plan() -> Plan:
    return plan_json(FIXTURES / "plan.json")
