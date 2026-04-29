from __future__ import annotations

import json

import click

import terra


@click.group()
def main() -> None:
    """terra — notebook-native Terraform analysis toolkit."""


@main.command()
@click.argument("plan_json_path")
def summary(plan_json_path: str) -> None:
    """Print add/change/destroy counts for a plan JSON file."""
    plan = terra.load.plan_json(plan_json_path)
    counts = terra.frame.summary(plan)
    click.echo(json.dumps(counts, indent=2))


@main.command("resources")
@click.argument("state_path")
def resources_cmd(state_path: str) -> None:
    """Print resources table for a local state file."""
    state = terra.load.state_local(state_path)
    df = terra.frame.resources_df(state)
    click.echo(df.to_string())


@main.command("risk")
@click.argument("plan_json_path")
@click.option("--high-only", is_flag=True, default=False, help="Only show high-risk changes.")
def risk_cmd(plan_json_path: str, high_only: bool) -> None:
    """Score changes in a plan JSON file for risk."""
    plan = terra.load.plan_json(plan_json_path)
    changes = terra.frame.changes_df(plan)
    scored = terra.risk.score(changes)
    if high_only:
        scored = scored[scored["risk"] == "high"]
    cols = ["address", "type", "actions", "risk", "risk_reasons"]
    click.echo(scored[cols].to_string())
