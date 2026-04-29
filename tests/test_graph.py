from __future__ import annotations

import sys

import networkx as nx
import pytest

from terra.graph.build import from_plan, from_state
from terra.schema.state import State


class TestFromState:
    def test_returns_digraph(self, state):
        g = from_state(state)
        assert isinstance(g, nx.DiGraph)

    def test_node_count(self, state):
        g = from_state(state)
        assert g.number_of_nodes() == 4

    def test_edge_count(self, state):
        g = from_state(state)
        assert g.number_of_edges() == 1

    def test_dependency_edge(self, state):
        g = from_state(state)
        assert g.has_edge(
            "module.networking.aws_subnet.public",
            "module.networking.aws_vpc.main",
        )

    def test_node_attributes(self, state):
        g = from_state(state)
        attrs = g.nodes["aws_s3_bucket.assets"]
        assert attrs["type"] == "aws_s3_bucket"
        assert attrs["name"] == "assets"
        assert attrs["mode"] == "managed"
        assert attrs["module"] == ""

    def test_child_module_node_attributes(self, state):
        g = from_state(state)
        attrs = g.nodes["module.networking.aws_vpc.main"]
        assert attrs["type"] == "aws_vpc"
        assert attrs["module"] == "module.networking"

    def test_all_expected_nodes_present(self, state):
        g = from_state(state)
        expected = {
            "aws_s3_bucket.assets",
            "aws_iam_role.lambda_exec",
            "module.networking.aws_vpc.main",
            "module.networking.aws_subnet.public",
        }
        assert set(g.nodes) == expected

    def test_empty_state_returns_empty_graph(self):
        empty = State(format_version="4")
        g = from_state(empty)
        assert g.number_of_nodes() == 0
        assert g.number_of_edges() == 0


class TestFromPlan:
    def test_returns_digraph(self, plan):
        g = from_plan(plan)
        assert isinstance(g, nx.DiGraph)

    def test_node_count(self, plan):
        g = from_plan(plan)
        assert g.number_of_nodes() == 4

    def test_no_edges_in_fixture(self, plan):
        # fixture config expressions have only constant_value, no references
        g = from_plan(plan)
        assert g.number_of_edges() == 0

    def test_all_expected_nodes_present(self, plan):
        g = from_plan(plan)
        expected = {
            "aws_s3_bucket.logs",
            "aws_iam_role.lambda_exec",
            "aws_rds_cluster.db",
            "data.aws_caller_identity.current",
        }
        assert set(g.nodes) == expected

    def test_node_actions_create(self, plan):
        g = from_plan(plan)
        assert g.nodes["aws_s3_bucket.logs"]["actions"] == ["create"]

    def test_node_actions_delete(self, plan):
        g = from_plan(plan)
        assert g.nodes["aws_rds_cluster.db"]["actions"] == ["delete"]

    def test_node_actions_update(self, plan):
        g = from_plan(plan)
        assert g.nodes["aws_iam_role.lambda_exec"]["actions"] == ["update"]

    def test_node_actions_noop(self, plan):
        g = from_plan(plan)
        assert g.nodes["data.aws_caller_identity.current"]["actions"] == ["no-op"]


class TestRender:
    def test_raises_import_error_without_ipycytoscape(self, state, monkeypatch):
        monkeypatch.setitem(sys.modules, "ipycytoscape", None)
        from terra.graph.render import render

        g = from_state(state)
        with pytest.raises(ImportError, match="ipycytoscape"):
            render(g)

    def test_render_returns_widget(self, state):
        pytest.importorskip("ipycytoscape")
        from terra.graph.render import render

        g = from_state(state)
        widget = render(g)
        assert hasattr(widget, "graph")
        assert len(widget.graph.nodes) == g.number_of_nodes()
