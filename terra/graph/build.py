from __future__ import annotations

import networkx as nx

from terra.frame._flatten import walk_modules
from terra.schema.plan import ConfigModule, Plan
from terra.schema.state import State


def from_state(state: State) -> nx.DiGraph:  # type: ignore[type-arg]
    """Build a DiGraph from a State's resource dependency fields."""
    g: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]
    if state.values is None:
        return g

    for module_addr, resource in walk_modules(state.values.root_module):
        g.add_node(
            resource.address,
            address=resource.address,
            type=resource.type,
            name=resource.name,
            module=module_addr,
            provider=resource.provider_name,
            mode=str(resource.mode),
        )

    for _module_addr, resource in walk_modules(state.values.root_module):
        for dep in resource.dependencies:
            if dep in g:
                g.add_edge(resource.address, dep)

    return g


def from_plan(plan: Plan) -> nx.DiGraph:  # type: ignore[type-arg]
    """Build a DiGraph from a Plan's resource changes and configuration references."""
    g: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]

    for rc in plan.resource_changes:
        g.add_node(
            rc.address,
            address=rc.address,
            type=rc.type,
            name=rc.name,
            module=rc.module_address or "",
            provider=rc.provider_name,
            actions=[str(a) for a in rc.change.actions],
        )

    _add_config_edges(g, plan.configuration.root_module)

    return g


def _add_config_edges(
    g: nx.DiGraph,  # type: ignore[type-arg]
    config_module: ConfigModule,
) -> None:
    for res_config in config_module.resources:
        if res_config.address not in g:
            continue
        for expr_value in res_config.expressions.values():
            if isinstance(expr_value, dict):
                for ref in expr_value.get("references", []):
                    if ref in g:
                        g.add_edge(res_config.address, ref)
