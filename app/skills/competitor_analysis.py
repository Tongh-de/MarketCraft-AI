from app.domain.creation import (
    CompetitorAnalysisRequest,
    CompetitorPluginResult,
    CreativeCapability,
    SkillDescriptor,
)
from app.plugins.registry import CreativePluginRegistry


class CompetitorVisualAnalysisSkill:
    descriptor = SkillDescriptor(
        skill_id="competitor-visual-analysis",
        name="竞品视觉分析 Skill",
        description="分析竞品视觉规律，输出差异维度和原创创作方案。",
        version="1.0.0",
        required_capabilities=[CreativeCapability.COMPETITOR_ANALYSIS],
    )

    def execute(
        self,
        request: CompetitorAnalysisRequest,
        plugin_registry: CreativePluginRegistry,
    ) -> CompetitorPluginResult:
        plugin = plugin_registry.select(
            {CreativeCapability.COMPETITOR_ANALYSIS},
            request.preferred_plugin_id,
        )
        return plugin.analyze_competitors(request)
