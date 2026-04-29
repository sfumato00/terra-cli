"""Tests for terra CLI commands."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from terra.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestSummaryCommand:
    def test_outputs_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["summary", str(FIXTURES / "plan.json")])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["add"] == 1
        assert data["change"] == 1
        assert data["destroy"] == 1
        assert data["no-op"] == 1

    def test_all_keys_present(self):
        runner = CliRunner()
        result = runner.invoke(main, ["summary", str(FIXTURES / "plan.json")])
        data = json.loads(result.output)
        assert set(data.keys()) >= {"add", "change", "destroy", "no-op"}


class TestResourcesCommand:
    def test_outputs_table(self):
        runner = CliRunner()
        result = runner.invoke(main, ["resources", str(FIXTURES / "state.json")])
        assert result.exit_code == 0
        assert "aws_s3_bucket" in result.output

    def test_contains_all_resources(self):
        runner = CliRunner()
        result = runner.invoke(main, ["resources", str(FIXTURES / "state.json")])
        assert "aws_iam_role" in result.output
        assert "aws_vpc" in result.output


class TestRiskCommand:
    def test_outputs_risk_table(self):
        runner = CliRunner()
        result = runner.invoke(main, ["risk", str(FIXTURES / "plan.json")])
        assert result.exit_code == 0
        assert "aws_rds_cluster.db" in result.output
        assert "high" in result.output

    def test_high_only_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["risk", "--high-only", str(FIXTURES / "plan.json")])
        assert result.exit_code == 0
        # Only high-risk rows; iam_role tag update (low) should not appear
        assert "aws_rds_cluster.db" in result.output

    def test_high_only_excludes_low(self):
        runner = CliRunner()
        result = runner.invoke(main, ["risk", "--high-only", str(FIXTURES / "plan.json")])
        # aws_iam_role.lambda_exec is a tag-only update (low risk)
        assert "aws_iam_role.lambda_exec" not in result.output
