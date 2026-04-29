from __future__ import annotations

import networkx as nx

_TYPE_COLORS: dict[str, str] = {
    "aws_s3": "#FF9900",
    "aws_iam": "#DD344C",
    "aws_rds": "#527FFF",
    "aws_vpc": "#8C4FFF",
    "aws_subnet": "#1A9C3E",
    "aws_lambda": "#F58536",
    "aws_ec2": "#F58536",
    "kubernetes": "#326CE5",
    "google": "#4285F4",
    "azurerm": "#0078D4",
}

_DEFAULT_COLOR = "#888888"


def _node_color(node_type: str) -> str:
    for prefix, color in _TYPE_COLORS.items():
        if node_type.startswith(prefix):
            return color
    return _DEFAULT_COLOR


def render(g: nx.DiGraph) -> object:  # type: ignore[type-arg]
    """Return an ipycytoscape CytoscapeWidget for the dependency graph.

    Raises ImportError if ipycytoscape is not installed (pip install 'terra-tf[notebook]').
    """
    try:
        import ipycytoscape  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "ipycytoscape is required for graph rendering. "
            "Install it with: pip install 'terra-tf[notebook]'"
        ) from exc

    widget = ipycytoscape.CytoscapeWidget()
    widget.graph.add_graph_from_networkx(g, directed=True)

    for node in widget.graph.nodes:
        node_id: str = node.data["id"]
        node_type: str = g.nodes[node_id].get("type", "")
        node.data["color"] = _node_color(node_type)
        node.data["label"] = g.nodes[node_id].get("address", node_id)

    widget.set_style(
        [
            {
                "selector": "node",
                "css": {
                    "content": "data(label)",
                    "background-color": "data(color)",
                    "color": "#ffffff",
                    "font-size": "10px",
                    "text-wrap": "wrap",
                    "text-max-width": "80px",
                },
            },
            {
                "selector": "edge",
                "css": {
                    "line-color": "#aaaaaa",
                    "target-arrow-color": "#aaaaaa",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                },
            },
            {
                "selector": "node:selected",
                "css": {
                    "background-color": "#FFD700",
                    "border-width": "2px",
                    "border-color": "#000000",
                },
            },
        ]
    )

    widget.set_layout(name="cose")
    return widget
