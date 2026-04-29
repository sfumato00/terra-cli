import pandas as pd

from terra.frame import changes_df, resources_df, summary
from terra.schema.plan import Plan
from terra.schema.state import State


class TestResourcesDf:
    def test_returns_dataframe(self, state: State) -> None:
        df = resources_df(state)
        assert isinstance(df, pd.DataFrame)

    def test_row_count(self, state: State) -> None:
        df = resources_df(state)
        # 2 root + 2 child_module = 4 total
        assert len(df) == 4

    def test_columns(self, state: State) -> None:
        df = resources_df(state)
        for col in ("address", "type", "name", "provider", "module", "mode"):
            assert col in df.columns

    def test_module_address(self, state: State) -> None:
        df = resources_df(state)
        net_rows = df[df["module"] == "module.networking"]
        assert len(net_rows) == 2

    def test_root_module_address(self, state: State) -> None:
        df = resources_df(state)
        root_rows = df[df["module"] == ""]
        assert len(root_rows) == 2

    def test_s3_query(self, state: State) -> None:
        df = resources_df(state)
        result = df.query("type == 'aws_s3_bucket'")
        assert len(result) == 1

    def test_empty_state(self) -> None:
        from terra.schema.state import State

        empty = State(format_version="4")
        df = resources_df(empty)
        assert len(df) == 0

    def test_dependencies_column(self, state: State) -> None:
        df = resources_df(state)
        subnet = df[df["address"] == "module.networking.aws_subnet.public"].iloc[0]
        assert "module.networking.aws_vpc.main" in subnet["dependencies"]


class TestChangesDf:
    def test_returns_dataframe(self, plan: Plan) -> None:
        df = changes_df(plan)
        assert isinstance(df, pd.DataFrame)

    def test_row_count(self, plan: Plan) -> None:
        df = changes_df(plan)
        assert len(df) == 4

    def test_columns(self, plan: Plan) -> None:
        df = changes_df(plan)
        for col in ("address", "type", "actions", "attr_diff"):
            assert col in df.columns

    def test_attr_diff_on_update(self, plan: Plan) -> None:
        df = changes_df(plan)
        update = df[df["address"] == "aws_iam_role.lambda_exec"].iloc[0]
        assert "tags" in update["attr_diff"]

    def test_no_attr_diff_on_noop(self, plan: Plan) -> None:
        df = changes_df(plan)
        noop = df[df["address"] == "data.aws_caller_identity.current"].iloc[0]
        assert list(noop["attr_diff"]) == []

    def test_empty_plan(self) -> None:
        from terra.schema.plan import Plan

        empty = Plan(format_version="1.2")
        df = changes_df(empty)
        assert len(df) == 0


class TestSummary:
    def test_counts(self, plan: Plan) -> None:
        s = summary(plan)
        assert s["add"] == 1
        assert s["change"] == 1
        assert s["destroy"] == 1
        assert s["no-op"] == 1

    def test_returns_dict(self, plan: Plan) -> None:
        s = summary(plan)
        assert isinstance(s, dict)
        assert set(s.keys()) >= {"add", "change", "destroy", "no-op"}
