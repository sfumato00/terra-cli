from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import Action, Mode


class ResourceChange(BaseModel):
    model_config = ConfigDict(extra="allow")

    address: str
    module_address: str | None = None
    mode: Mode = Mode.MANAGED
    type: str
    name: str
    provider_name: str
    change: Change


class Change(BaseModel):
    model_config = ConfigDict(extra="allow")

    actions: list[Action]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    after_unknown: dict[str, Any] = Field(default_factory=dict)
    before_sensitive: dict[str, Any] | bool = Field(default_factory=dict)
    after_sensitive: dict[str, Any] | bool = Field(default_factory=dict)


class Expression(BaseModel):
    model_config = ConfigDict(extra="allow")

    references: list[str] = Field(default_factory=list)


class ConfigResource(BaseModel):
    model_config = ConfigDict(extra="allow")

    address: str
    mode: Mode = Mode.MANAGED
    type: str
    name: str
    provider_config_key: str = ""
    expressions: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 0


class ConfigModule(BaseModel):
    model_config = ConfigDict(extra="allow")

    resources: list[ConfigResource] = Field(default_factory=list)
    module_calls: dict[str, Any] = Field(default_factory=dict)


class Configuration(BaseModel):
    model_config = ConfigDict(extra="allow")

    root_module: ConfigModule = Field(default_factory=ConfigModule)
    provider_config: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    model_config = ConfigDict(extra="allow")

    format_version: str = "1.2"
    terraform_version: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    planned_values: Any = None
    resource_changes: list[ResourceChange] = Field(default_factory=list)
    output_changes: dict[str, Any] = Field(default_factory=dict)
    prior_state: Any = None
    configuration: Configuration = Field(default_factory=Configuration)
    relevant_attributes: list[Any] = Field(default_factory=list)
    timestamp: str | None = None
