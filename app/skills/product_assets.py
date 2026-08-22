from app.domain.creation import (
    CreateCreationTaskRequest,
    CreativeAssetKind,
    CreativeCapability,
    SkillDescriptor,
    SkillExecutionResult,
)
from app.plugins.registry import CreativePluginRegistry
from app.skills.base import EcommerceSkill

OUTPUT_CAPABILITIES = {
    CreativeAssetKind.FRONT_VIEW: CreativeCapability.MULTI_VIEW_GENERATION,
    CreativeAssetKind.SIDE_VIEW: CreativeCapability.MULTI_VIEW_GENERATION,
    CreativeAssetKind.BACK_VIEW: CreativeCapability.MULTI_VIEW_GENERATION,
    CreativeAssetKind.DETAIL_VIEW: CreativeCapability.MULTI_VIEW_GENERATION,
    CreativeAssetKind.MODEL_TRY_ON: CreativeCapability.VIRTUAL_TRY_ON,
    CreativeAssetKind.POSTER: CreativeCapability.POSTER_GENERATION,
    CreativeAssetKind.SHORT_VIDEO: CreativeCapability.VIDEO_GENERATION,
}


class ProductAssetGenerationSkill(EcommerceSkill):
    descriptor = SkillDescriptor(
        skill_id="product-asset-generation",
        name="商品素材生成 Skill",
        description="从一张商品图生成多角度图、模特试穿图、海报和短视频素材。",
        version="1.0.0",
        required_capabilities=[
            CreativeCapability.MULTI_VIEW_GENERATION,
            CreativeCapability.VIRTUAL_TRY_ON,
        ],
    )

    def execute(
        self,
        request: CreateCreationTaskRequest,
        plugin_registry: CreativePluginRegistry,
    ) -> SkillExecutionResult:
        capabilities = {OUTPUT_CAPABILITIES[item] for item in request.requested_outputs}
        plugin = plugin_registry.select(capabilities, request.preferred_plugin_id)
        assets = plugin.generate_assets(
            request.product,
            request.instruction,
            request.requested_outputs,
        )
        return SkillExecutionResult(
            plugin_id=plugin.descriptor.plugin_id,
            assets=assets,
            trace=[
                "validate_product_input",
                "lock_source_product_identity",
                f"select_plugin:{plugin.descriptor.plugin_id}",
                "generate_requested_assets",
                "validate_asset_manifest",
            ],
        )
