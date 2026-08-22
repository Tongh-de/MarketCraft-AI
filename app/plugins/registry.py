from functools import lru_cache

from app.domain.creation import CreativeCapability, PluginDescriptor
from app.plugins.base import CreativePlugin, CreativePluginError
from app.plugins.mock_competitor_vision import MockCompetitorVisionPlugin
from app.plugins.mock_creative import (
    build_mock_comfyui_plugin,
    build_mock_jimeng_plugin,
)


class CreativePluginRegistry:
    def __init__(self, plugins: list[CreativePlugin] | None = None) -> None:
        installed = plugins or [
            build_mock_comfyui_plugin(),
            build_mock_jimeng_plugin(),
            MockCompetitorVisionPlugin(),
        ]
        self._plugins = {plugin.descriptor.plugin_id: plugin for plugin in installed}

    def list_descriptors(self) -> list[PluginDescriptor]:
        return [plugin.descriptor for plugin in self._plugins.values()]

    def select(
        self,
        required_capabilities: set[CreativeCapability],
        preferred_plugin_id: str | None = None,
    ) -> CreativePlugin:
        if preferred_plugin_id:
            plugin = self._plugins.get(preferred_plugin_id)
            if not plugin:
                raise CreativePluginError(f"creative plugin not found: {preferred_plugin_id}")
            available = set(plugin.descriptor.capabilities)
            if not required_capabilities.issubset(available):
                raise CreativePluginError(
                    f"plugin {preferred_plugin_id} does not support all requested outputs"
                )
            return plugin

        for plugin in self._plugins.values():
            if required_capabilities.issubset(set(plugin.descriptor.capabilities)):
                return plugin
        raise CreativePluginError("no installed creative plugin supports this request")


@lru_cache
def get_creative_plugin_registry() -> CreativePluginRegistry:
    return CreativePluginRegistry()
