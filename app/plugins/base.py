from app.domain.creation import (
    CompetitorAnalysisRequest,
    CompetitorPluginResult,
    CreativeAssetKind,
    CreativeProductInput,
    GeneratedCreativeAsset,
    PluginDescriptor,
)


class CreativePluginError(Exception):
    pass


class CreativePlugin:
    descriptor: PluginDescriptor

    def generate_assets(
        self,
        product: CreativeProductInput,
        instruction: str,
        requested_outputs: list[CreativeAssetKind],
    ) -> list[GeneratedCreativeAsset]:
        raise CreativePluginError("plugin does not support creative asset generation")

    def analyze_competitors(
        self, request: CompetitorAnalysisRequest
    ) -> CompetitorPluginResult:
        raise CreativePluginError("plugin does not support competitor analysis")
