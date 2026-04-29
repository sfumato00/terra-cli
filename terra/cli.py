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
