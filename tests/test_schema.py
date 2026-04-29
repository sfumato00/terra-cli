from terra.schema.common import Action, Mode
from terra.schema.plan import Plan
from terra.schema.state import State


def test_state_parses(state: State) -> None:
    assert state.format_version == "4"
    assert state.values is not None
    root = state.values.root_module
    assert len(root.resources) == 2
    assert len(root.child_modules) == 1


def test_state_resource_fields(state: State) -> None:
    res = state.values.root_module.resources[0]  # type: ignore[union-attr]
    assert res.address == "aws_s3_bucket.assets"
    assert res.type == "aws_s3_bucket"
    assert res.mode == Mode.MANAGED


def test_state_child_module(state: State) -> None:
    child = state.values.root_module.child_modules[0]  # type: ignore[union-attr]
    assert child.address == "module.networking"
    assert len(child.resources) == 2
    subnet = child.resources[1]
    assert subnet.dependencies == ["module.networking.aws_vpc.main"]


def test_plan_parses(plan: Plan) -> None:
    assert plan.format_version == "1.2"
    assert len(plan.resource_changes) == 4


def test_plan_actions(plan: Plan) -> None:
    rc_map = {rc.address: rc for rc in plan.resource_changes}
    assert rc_map["aws_s3_bucket.logs"].change.actions == [Action.CREATE]
    assert rc_map["aws_iam_role.lambda_exec"].change.actions == [Action.UPDATE]
    assert rc_map["aws_rds_cluster.db"].change.actions == [Action.DELETE]
    assert rc_map["data.aws_caller_identity.current"].change.actions == [Action.NO_OP]


def test_plan_mode(plan: Plan) -> None:
    data_rc = next(rc for rc in plan.resource_changes if rc.mode == Mode.DATA)
    assert data_rc.address == "data.aws_caller_identity.current"


def test_plan_configuration(plan: Plan) -> None:
    assert len(plan.configuration.root_module.resources) == 2
    assert "aws" in plan.configuration.provider_config
