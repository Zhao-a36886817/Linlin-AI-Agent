from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

KNOWN_CAPABILITIES = frozenset({"tools", "workspace:read", "workspace:write", "network", "credentials"})
PLUGIN_SCHEMA_VERSION = 1
PLUGIN_SDK_VERSION = 1


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(
        default=PLUGIN_SCHEMA_VERSION,
        ge=PLUGIN_SCHEMA_VERSION,
        le=PLUGIN_SCHEMA_VERSION,
    )
    plugin_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    sdk_version: int = Field(
        default=PLUGIN_SDK_VERSION,
        ge=PLUGIN_SDK_VERSION,
        le=PLUGIN_SDK_VERSION,
    )
    capabilities: tuple[str, ...] = Field(default=(), max_length=16)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Plugin capabilities must be unique.")
        unknown = set(value) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(f"Unknown plugin capabilities: {sorted(unknown)}")
        return tuple(sorted(value))
