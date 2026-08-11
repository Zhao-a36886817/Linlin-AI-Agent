import pytest
from pydantic import ValidationError

from app.plugins import (
    PLUGIN_SCHEMA_VERSION,
    PLUGIN_SDK_VERSION,
    PluginError,
    PluginManifest,
    PluginPermissionError,
    PluginRuntime,
)


def manifest(**overrides: object) -> PluginManifest:
    values: dict[str, object] = {"plugin_id": "example-plugin", "version": "1.0.0", "capabilities": ("tools",)}
    values.update(overrides)
    return PluginManifest.model_validate(values)


def test_hostile_or_incompatible_manifests_are_rejected() -> None:
    for values in (
        {"plugin_id": "../escape"},
        {"sdk_version": 2},
        {"capabilities": ("arbitrary-code",)},
        {"capabilities": ("tools", "tools")},
    ):
        with pytest.raises(ValidationError):
            manifest(**values)


def test_published_plugin_contract_versions_are_stable() -> None:
    value = manifest()
    assert PLUGIN_SCHEMA_VERSION == 1
    assert PLUGIN_SDK_VERSION == 1
    assert value.schema_version == PLUGIN_SCHEMA_VERSION
    assert value.sdk_version == PLUGIN_SDK_VERSION


def test_unapproved_capabilities_are_rejected() -> None:
    with pytest.raises(PluginPermissionError):
        PluginRuntime().install(manifest(), approved_capabilities=set())


def test_plugins_are_disabled_after_install() -> None:
    runtime = PluginRuntime()
    runtime.install(manifest(), approved_capabilities={"tools"})
    assert runtime.capabilities("example-plugin") == ()


def test_lifecycle_is_deterministic() -> None:
    runtime = PluginRuntime()
    runtime.install(manifest(), approved_capabilities={"tools"})
    runtime.enable("example-plugin")
    assert runtime.capabilities("example-plugin") == ("tools",)
    runtime.disable("example-plugin")
    assert runtime.capabilities("example-plugin") == ()
    assert runtime.uninstall("example-plugin") is True
    assert runtime.uninstall("example-plugin") is False


def test_duplicate_install_and_unknown_enable_fail() -> None:
    runtime = PluginRuntime()
    runtime.install(manifest(), approved_capabilities={"tools"})
    with pytest.raises(PluginError):
        runtime.install(manifest(), approved_capabilities={"tools"})
    with pytest.raises(PluginError):
        runtime.enable("missing")
