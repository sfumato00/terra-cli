from __future__ import annotations

from collections.abc import Iterator

from terra.schema.state import Module, Resource


def walk_modules(module: Module, prefix: str = "") -> Iterator[tuple[str, Resource]]:
    """Yield (module_address, resource) pairs, recursing into child_modules."""
    module_addr = module.address or prefix
    for resource in module.resources:
        yield module_addr, resource
    for child in module.child_modules:
        yield from walk_modules(child, child.address or "")
