from abc import ABC, abstractmethod

from app.domain.creation import (
    CreativeAssetKind,
    CreativeProductInput,
    GeneratedCreativeAsset,
    PluginDescriptor,
)


class CreativePluginError(Exception):
    pass


class CreativePlugin(ABC):
    descriptor: PluginDescriptor

    @abstractmethod
    def generate_assets(
        self,
        product: CreativeProductInput,
        instruction: str,
        requested_outputs: list[CreativeAssetKind],
    ) -> list[GeneratedCreativeAsset]: ...
