import pandas as pd

from terra.frame import changes_df, resources_df, state_diff, summary
from terra.schema.plan import Plan
from terra.schema.state import Module, Resource, State, StateValues
from terra.schema.common import Mode


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


class TestStateDiff:
    def _make_state(self, resources: list[dict]) -> State:
        rs = [
            Resource(
                address=r["address"],
                mode=Mode.MANAGED,
                type=r["type"],
                name=r["address"].split(".")[-1],
                provider_name="registry.terraform.io/hashicorp/aws",
                values=r.get("values", {}),
            )
            for r in resources
        ]
        return State(
            format_version="4",
            values=StateValues(root_module=Module(resources=rs)),
        )

    def test_added_resource(self) -> None:
        before = self._make_state([{"address": "aws_s3_bucket.a", "type": "aws_s3_bucket"}])
        after = self._make_state([
            {"address": "aws_s3_bucket.a", "type": "aws_s3_bucket"},
            {"address": "aws_s3_bucket.b", "type": "aws_s3_bucket"},
        ])
        df = state_diff(before, after)
        added = df[df["address"] == "aws_s3_bucket.b"]
        assert len(added) == 1
        assert added.iloc[0]["diff_type"] == "added"

    def test_removed_resource(self) -> None:
        before = self._make_state([
            {"address": "aws_s3_bucket.a", "type": "aws_s3_bucket"},
            {"address": "aws_s3_bucket.b", "type": "aws_s3_bucket"},
        ])
        after = self._make_state([{"address": "aws_s3_bucket.a", "type": "aws_s3_bucket"}])
        df = state_diff(before, after)
        removed = df[df["address"] == "aws_s3_bucket.b"]
        assert len(removed) == 1
        assert removed.iloc[0]["diff_type"] == "removed"

    def test_changed_resource(self) -> None:
        before = self._make_state([
            {"address": "aws_s3_bucket.a", "type": "aws_s3_bucket", "values": {"region": "us-east-1"}}
        ])
        after = self._make_state([
            {"address": "aws_s3_bucket.a", "type": "aws_s3_bucket", "values": {"region": "us-west-2"}}
        ])
        df = state_diff(before, after)
        changed = df[df["address"] == "aws_s3_bucket.a"]
        assert len(changed) == 1
        assert changed.iloc[0]["diff_type"] == "changed"
        assert "region" in changed.iloc[0]["changed_attrs"]

    def test_unchanged_resource_not_in_diff(self) -> None:
        before = self._make_state([
            {"address": "aws_s3_bucket.a", "type": "aws_s3_bucket", "values": {"region": "us-east-1"}}
        ])
        after = self._make_state([
            {"address": "aws_s3_bucket.a", "type": "aws_s3_bucket", "values": {"region": "us-east-1"}}
        ])
        df = state_diff(before, after)
        assert len(df) == 0

    def test_empty_states(self) -> None:
        empty = State(format_version="4")
        df = state_diff(empty, empty)
        assert len(df) == 0
        assert "address" in df.columns
        assert "diff_type" in df.columns

    def test_fixture_states_are_identical(self, state: State) -> None:
        df = state_diff(state, state)
        assert len(df) == 0

    def test_columns_present(self) -> None:
        before = self._make_state([{"address": "aws_s3_bucket.a", "type": "aws_s3_bucket"}])
        after = self._make_state([])
        df = state_diff(before, after)
        for col in ("address", "diff_type", "changed_attrs"):
            assert col in df.columns


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
