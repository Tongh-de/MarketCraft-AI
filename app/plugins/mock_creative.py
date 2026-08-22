import hashlib
from uuid import NAMESPACE_URL, uuid5

from app.domain.creation import (
    CreativeAssetKind,
    CreativeCapability,
    CreativeProductInput,
    GeneratedCreativeAsset,
    PluginDescriptor,
    PluginMode,
    PluginStatus,
)
from app.plugins.base import CreativePlugin

ASSET_LABELS = {
    CreativeAssetKind.FRONT_VIEW: "商品正面图",
    CreativeAssetKind.SIDE_VIEW: "商品侧面图",
    CreativeAssetKind.BACK_VIEW: "商品背面图",
    CreativeAssetKind.DETAIL_VIEW: "商品细节图",
    CreativeAssetKind.MODEL_TRY_ON: "模特试穿图",
    CreativeAssetKind.POSTER: "商品营销海报",
    CreativeAssetKind.SHORT_VIDEO: "15秒商品视频",
}


class MockCreativePlugin(CreativePlugin):
    def __init__(self, descriptor: PluginDescriptor) -> None:
        self.descriptor = descriptor

    def generate_assets(
        self,
        product: CreativeProductInput,
        instruction: str,
        requested_outputs: list[CreativeAssetKind],
    ) -> list[GeneratedCreativeAsset]:
        seed = hashlib.sha256(
            f"{self.descriptor.plugin_id}:{product.sku}:{instruction}".encode()
        ).hexdigest()[:16]
        assets: list[GeneratedCreativeAsset] = []
        for kind in requested_outputs:
            token = f"{seed}-{kind.value}"
            assets.append(
                GeneratedCreativeAsset(
                    asset_id=uuid5(NAMESPACE_URL, token),
                    kind=kind,
                    label=ASSET_LABELS[kind],
                    url=f"/api/v1/creation/mock-assets/{token}.svg",
                    provider=self.descriptor.plugin_id,
                    mock=True,
                    metadata={
                        "source_sku": product.sku,
                        "consistency_guard": "source_product_locked",
                        "generation_mode": "mock",
                    },
                )
            )
        return assets


def build_mock_comfyui_plugin() -> MockCreativePlugin:
    return MockCreativePlugin(
        PluginDescriptor(
            plugin_id="comfyui.mock",
            name="ComfyUI",
            description="可替换为 ComfyUI HTTP 与 WebSocket 工作流适配器。",
            mode=PluginMode.MOCK,
            status=PluginStatus.CONNECTED,
            capabilities=[
                CreativeCapability.MULTI_VIEW_GENERATION,
                CreativeCapability.VIRTUAL_TRY_ON,
                CreativeCapability.POSTER_GENERATION,
            ],
        )
    )


def build_mock_jimeng_plugin() -> MockCreativePlugin:
    return MockCreativePlugin(
        PluginDescriptor(
            plugin_id="jimeng.mock",
            name="即梦 AI",
            description="即梦 AI 的演示适配器，正式接入取决于可用的官方 API 授权。",
            mode=PluginMode.MOCK,
            status=PluginStatus.CONNECTED,
            capabilities=[
                CreativeCapability.MULTI_VIEW_GENERATION,
                CreativeCapability.VIRTUAL_TRY_ON,
                CreativeCapability.POSTER_GENERATION,
                CreativeCapability.VIDEO_GENERATION,
            ],
        )
    )
