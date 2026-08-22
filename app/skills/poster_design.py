from app.domain.creation import (
    CreativeCapability,
    PluginMode,
    PosterProjectRequest,
    PosterSkillResult,
    SkillDescriptor,
)
from app.plugins.registry import CreativePluginRegistry


class PosterDesignSkill:
    descriptor = SkillDescriptor(
        skill_id="poster-design",
        name="AI 海报设计 Skill",
        description="选择生成插件并建立可编辑的商品海报布局、文案和品牌约束。",
        version="1.0.0",
        required_capabilities=[CreativeCapability.POSTER_GENERATION],
    )

    def execute(
        self,
        request: PosterProjectRequest,
        plugin_registry: CreativePluginRegistry,
    ) -> PosterSkillResult:
        plugin = plugin_registry.select(
            {CreativeCapability.POSTER_GENERATION},
            request.preferred_plugin_id,
        )
        prompt = (
            f"为{request.product.name}设计{request.style.value}风格的电商海报；"
            f"画布预设为{request.preset.value}；标题：{request.title}；"
            f"副标题：{request.subtitle or '无'}；保持商品颜色、版型和标识准确；"
            "背景与文字必须保持可编辑图层，不虚构商品功效、参数或认证。"
        )
        return PosterSkillResult(
            plugin_id=plugin.descriptor.plugin_id,
            generation_prompt=prompt,
            trace=[
                "validate_poster_input",
                "lock_product_identity",
                f"select_plugin:{plugin.descriptor.plugin_id}",
                "build_editable_layout",
                "apply_brand_colors",
                "create_poster_draft",
            ],
            mock=plugin.descriptor.mode == PluginMode.MOCK,
        )
