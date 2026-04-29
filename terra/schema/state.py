from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import Mode


class Resource(BaseModel):
    model_config = ConfigDict(extra="allow")

    address: str
    mode: Mode
    type: str
    name: str
    provider_name: str
    schema_version: int = 0
    values: dict[str, Any] = Field(default_factory=dict)
    sensitive_values: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)


class Module(BaseModel):
    model_config = ConfigDict(extra="allow")

    resources: list[Resource] = Field(default_factory=list)
    child_modules: list[Module] = Field(default_factory=list)
    address: str | None = None


class StateValues(BaseModel):
    model_config = ConfigDict(extra="allow")

    root_module: Module


class State(BaseModel):
    model_config = ConfigDict(extra="allow")

    format_version: str = "4"
    terraform_version: str | None = None
    serial: int | None = None
    lineage: str | None = None
    values: StateValues | None = None
