"""Tests for terra.risk — score, blast_radius, user_data_diff."""
from __future__ import annotations

import base64
import gzip
import json

import networkx as nx
import pandas as pd
import pytest

import terra
from terra.frame.changes import changes_df
from terra.risk import blast_radius, score, user_data_diff
from terra.risk.rules import apply_rules, register
from terra.schema.plan import Change, Plan, ResourceChange
from terra.schema.common import Action, Mode


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_plan(*resource_changes: ResourceChange) -> Plan:
    return Plan(resource_changes=list(resource_changes))


def _rc(
    address: str,
    rtype: str,
    actions: list[str],
    before: dict | None = None,
    after: dict | None = None,
) -> ResourceChange:
    return ResourceChange(
        address=address,
        type=rtype,
        name=address.split(".")[-1],
        provider_name="registry.terraform.io/hashicorp/aws",
        change=Change(
            actions=[Action(a) for a in actions],
            before=before,
            after=after,
        ),
    )


# ---------------------------------------------------------------------------
# changes_df: before/after columns are present
# ---------------------------------------------------------------------------

class TestChangesDfColumns:
    def test_before_after_columns_present(self, plan):
        df = changes_df(plan)
        assert "before" in df.columns
        assert "after" in df.columns

    def test_before_after_types(self, plan):
        df = changes_df(plan)
        for val in df["before"]:
            assert isinstance(val, dict)
        for val in df["after"]:
            assert isinstance(val, dict)

    def test_null_before_becomes_empty_dict(self, plan):
        # aws_s3_bucket.logs is a create — before is null
        row = df = changes_df(plan)
        create_row = df[df["address"] == "aws_s3_bucket.logs"].iloc[0]
        assert create_row["before"] == {}

    def test_null_after_becomes_empty_dict(self, plan):
        df = changes_df(plan)
        delete_row = df[df["address"] == "aws_rds_cluster.db"].iloc[0]
        assert delete_row["after"] == {}


# ---------------------------------------------------------------------------
# stateful_delete rule
# ---------------------------------------------------------------------------

class TestStatefulDelete:
    def test_rds_delete_is_high(self):
        plan = _make_plan(_rc("aws_rds_cluster.db", "aws_rds_cluster", ["delete"],
                               before={"id": "db"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"

    def test_s3_delete_is_high(self):
        plan = _make_plan(_rc("aws_s3_bucket.data", "aws_s3_bucket", ["delete"],
                               before={"bucket": "my-bucket"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"

    def test_s3_create_is_not_stateful_delete(self):
        plan = _make_plan(_rc("aws_s3_bucket.new", "aws_s3_bucket", ["create"],
                               after={"bucket": "new-bucket"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "none"

    def test_non_stateful_delete_is_none(self):
        plan = _make_plan(_rc("aws_lambda_function.fn", "aws_lambda_function", ["delete"],
                               before={"function_name": "fn"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "none"


# ---------------------------------------------------------------------------
# replace_no_cbd rule
# ---------------------------------------------------------------------------

class TestReplaceNoCbd:
    def test_destroy_then_create_is_high(self):
        plan = _make_plan(_rc("aws_instance.web", "aws_instance", ["delete", "create"],
                               before={"id": "i-1"}, after={"id": "i-2"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"
        assert any("destroy-before-create" in r for r in scored.iloc[0]["risk_reasons"])

    def test_create_then_destroy_is_not_flagged(self):
        plan = _make_plan(_rc("aws_instance.web", "aws_instance", ["create", "delete"],
                               before={"id": "i-1"}, after={"id": "i-2"}))
        df = changes_df(plan)
        scored = score(df)
        # create-before-destroy is safe — no replace_no_cbd trigger
        assert "destroy-before-create replace" not in " ".join(scored.iloc[0]["risk_reasons"])


# ---------------------------------------------------------------------------
# iam_widening rule
# ---------------------------------------------------------------------------

class TestIamWidening:
    def test_wildcard_added_is_high(self):
        before = {"policy": json.dumps({"Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::bucket"})}
        after = {"policy": json.dumps({"Action": ["*"], "Resource": "*"})}
        plan = _make_plan(_rc("aws_iam_policy.broad", "aws_iam_policy", ["update"],
                               before=before, after=after))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"

    def test_no_new_wildcard_is_not_flagged(self):
        before = {"policy": json.dumps({"Action": ["s3:GetObject"]})}
        after = {"policy": json.dumps({"Action": ["s3:GetObject", "s3:PutObject"]})}
        plan = _make_plan(_rc("aws_iam_policy.narrow", "aws_iam_policy", ["update"],
                               before=before, after=after))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "none"

    def test_non_iam_type_not_flagged(self):
        after = {"policy": json.dumps({"Action": ["*"]})}
        plan = _make_plan(_rc("aws_s3_bucket.x", "aws_s3_bucket", ["update"],
                               before={}, after=after))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "none"


# ---------------------------------------------------------------------------
# user_data_mutation rule
# ---------------------------------------------------------------------------

class TestUserDataMutation:
    def test_user_data_change_is_high(self):
        plan = _make_plan(_rc("aws_instance.app", "aws_instance", ["update"],
                               before={"user_data": "#!/bin/bash\necho old"},
                               after={"user_data": "#!/bin/bash\necho new"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"
        assert any("user_data" in r for r in scored.iloc[0]["risk_reasons"])

    def test_user_data_base64_change_is_high(self):
        plan = _make_plan(_rc("aws_instance.app", "aws_instance", ["update"],
                               before={"user_data_base64": base64.b64encode(b"old").decode()},
                               after={"user_data_base64": base64.b64encode(b"new").decode()}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"

    def test_non_instance_user_data_not_flagged(self):
        plan = _make_plan(_rc("aws_s3_bucket.x", "aws_s3_bucket", ["update"],
                               before={"user_data": "old"},
                               after={"user_data": "new"}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "none"


# ---------------------------------------------------------------------------
# tag_only_update rule
# ---------------------------------------------------------------------------

class TestTagOnlyUpdate:
    def test_tag_only_is_low(self):
        plan = _make_plan(_rc("aws_iam_role.r", "aws_iam_role", ["update"],
                               before={"name": "r", "tags": {}},
                               after={"name": "r", "tags": {"env": "prod"}}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "low"

    def test_mixed_change_not_tag_only(self):
        plan = _make_plan(_rc("aws_iam_role.r", "aws_iam_role", ["update"],
                               before={"name": "r", "tags": {}},
                               after={"name": "r2", "tags": {"env": "prod"}}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "none"

    def test_fixture_plan_iam_role_tag_update(self, plan):
        df = changes_df(plan)
        scored = score(df)
        iam_row = scored[scored["address"] == "aws_iam_role.lambda_exec"].iloc[0]
        assert iam_row["risk"] == "low"


# ---------------------------------------------------------------------------
# score: existing fixture
# ---------------------------------------------------------------------------

class TestScoreFixture:
    def test_rds_delete_is_high_in_fixture(self, plan):
        df = changes_df(plan)
        scored = score(df)
        rds_row = scored[scored["address"] == "aws_rds_cluster.db"].iloc[0]
        assert rds_row["risk"] == "high"

    def test_risk_reasons_is_list(self, plan):
        df = changes_df(plan)
        scored = score(df)
        for reasons in scored["risk_reasons"]:
            assert isinstance(reasons, list)

    def test_no_op_is_none(self, plan):
        df = changes_df(plan)
        scored = score(df)
        noop_row = scored[scored["address"] == "data.aws_caller_identity.current"].iloc[0]
        assert noop_row["risk"] == "none"

    def test_score_returns_all_columns(self, plan):
        df = changes_df(plan)
        scored = score(df)
        assert "risk" in scored.columns
        assert "risk_reasons" in scored.columns
        assert len(scored) == len(df)

    def test_empty_df_returns_with_risk_columns(self):
        empty = pd.DataFrame(columns=["address", "type", "actions", "attr_diff"])
        scored = score(empty)
        assert "risk" in scored.columns
        assert "risk_reasons" in scored.columns


# ---------------------------------------------------------------------------
# blast_radius
# ---------------------------------------------------------------------------

class TestBlastRadius:
    def _graph(self) -> nx.DiGraph:
        # Edges go dependent → dependency (terra's convention from build.py)
        # subnet depends on vpc, instance depends on subnet, tg depends on instance
        g = nx.DiGraph()
        g.add_edge("aws_subnet.public", "aws_vpc.main")
        g.add_edge("aws_instance.app", "aws_subnet.public")
        g.add_edge("aws_lb_target_group.tg", "aws_instance.app")
        return g

    def test_blast_radius_root_dependency(self):
        # Destroying vpc affects everything that transitively depends on it
        g = self._graph()
        result = blast_radius(g, "aws_vpc.main")
        assert "aws_subnet.public" in result
        assert "aws_instance.app" in result
        assert "aws_lb_target_group.tg" in result

    def test_blast_radius_root_node(self):
        # Nothing depends on the leaf dependent — empty blast radius
        g = self._graph()
        result = blast_radius(g, "aws_lb_target_group.tg")
        assert result == set()

    def test_blast_radius_unknown_node(self):
        g = self._graph()
        result = blast_radius(g, "aws_nonexistent.x")
        assert result == set()

    def test_blast_radius_state_graph(self, state):
        # state.json: subnet depends on vpc (edge: subnet → vpc)
        # destroying vpc → subnet is in blast radius
        g = terra.graph.from_state(state)
        result = blast_radius(g, "module.networking.aws_vpc.main")
        assert "module.networking.aws_subnet.public" in result


# ---------------------------------------------------------------------------
# user_data_diff
# ---------------------------------------------------------------------------

class TestUserDataDiff:
    def _plain_b64(self, text: str) -> str:
        return base64.b64encode(text.encode()).decode()

    def _gzip_b64(self, text: str) -> str:
        return base64.b64encode(gzip.compress(text.encode())).decode()

    def test_plain_base64_decoded(self):
        before_script = "#!/bin/bash\necho hello"
        after_script = "#!/bin/bash\necho world"
        plan = _make_plan(_rc("aws_instance.app", "aws_instance", ["update"],
                               before={"user_data_base64": self._plain_b64(before_script)},
                               after={"user_data_base64": self._plain_b64(after_script)}))
        df = changes_df(plan)
        results = user_data_diff(df)
        assert len(results) == 1
        assert results[0]["address"] == "aws_instance.app"
        assert results[0]["field"] == "user_data_base64"
        assert "hello" in results[0]["before_text"]
        assert "world" in results[0]["after_text"]
        assert "-" in results[0]["unified_diff"]

    def test_gzip_base64_decoded(self):
        before = self._gzip_b64("#cloud-config\npackages: [git]")
        after = self._gzip_b64("#cloud-config\npackages: [git, curl]")
        plan = _make_plan(_rc("aws_instance.app", "aws_instance", ["update"],
                               before={"user_data_base64": before},
                               after={"user_data_base64": after}))
        df = changes_df(plan)
        results = user_data_diff(df)
        assert len(results) == 1
        assert "git" in results[0]["before_text"]
        assert "curl" in results[0]["after_text"]

    def test_raw_user_data_not_base64(self):
        plan = _make_plan(_rc("aws_instance.app", "aws_instance", ["update"],
                               before={"user_data": "#!/bin/bash\necho old"},
                               after={"user_data": "#!/bin/bash\necho new"}))
        df = changes_df(plan)
        results = user_data_diff(df)
        assert len(results) == 1
        assert results[0]["field"] == "user_data"

    def test_no_user_data_change_returns_empty(self):
        plan = _make_plan(_rc("aws_instance.app", "aws_instance", ["update"],
                               before={"tags": {}}, after={"tags": {"env": "prod"}}))
        df = changes_df(plan)
        results = user_data_diff(df)
        assert results == []

    def test_empty_df_returns_empty(self):
        assert user_data_diff(pd.DataFrame()) == []


# ---------------------------------------------------------------------------
# register custom rule
# ---------------------------------------------------------------------------

class TestRegisterRule:
    def test_custom_rule_applied(self):
        @register
        def always_medium(row: pd.Series) -> tuple[str, str] | None:
            if row.get("type") == "custom_resource.special":
                return "high", "custom rule triggered"
            return None

        plan = _make_plan(_rc("custom_resource.special", "custom_resource.special",
                               ["update"], before={}, after={}))
        df = changes_df(plan)
        scored = score(df)
        assert scored.iloc[0]["risk"] == "high"
        assert "custom rule triggered" in scored.iloc[0]["risk_reasons"]
