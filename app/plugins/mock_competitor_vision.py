from app.domain.creation import (
    CompetitorAnalysisDimension,
    CompetitorAnalysisRequest,
    CompetitorPluginResult,
    CreativeCapability,
    DifferentiatedCreativeBrief,
    PluginDescriptor,
    PluginMode,
    PluginStatus,
)
from app.plugins.base import CreativePlugin


class MockCompetitorVisionPlugin(CreativePlugin):
    descriptor = PluginDescriptor(
        plugin_id="multimodal-vision.mock",
        name="多模态视觉分析",
        description="竞品构图、色彩、场景和文案分析的确定性演示插件。",
        mode=PluginMode.MOCK,
        status=PluginStatus.CONNECTED,
        capabilities=[CreativeCapability.COMPETITOR_ANALYSIS],
    )

    def analyze_competitors(
        self, request: CompetitorAnalysisRequest
    ) -> CompetitorPluginResult:
        product = request.product
        count = len(request.competitor_images)
        pending = "待真实视觉模型读取商品图片后验证"
        dimensions = [
            CompetitorAnalysisDimension(
                dimension="构图与主体占比",
                competitor_pattern="演示假设：竞品通常使用居中构图和较高主体占比",
                own_product_gap=pending,
                recommendation="优先生成主体占画面 70%–85% 的干净主图版本",
                confidence=0.35,
            ),
            CompetitorAnalysisDimension(
                dimension="色彩与光影",
                competitor_pattern="演示假设：同品类常使用统一低饱和背景和柔光",
                own_product_gap=pending,
                recommendation="保持商品真实颜色，背景与品牌色形成可识别的对比",
                confidence=0.35,
            ),
            CompetitorAnalysisDimension(
                dimension="模特与使用场景",
                competitor_pattern="演示假设：场景图强调目标人群的真实使用状态",
                own_product_gap=pending,
                recommendation=f"围绕{product.target_audience}生成一个真实使用场景",
                confidence=0.35,
            ),
            CompetitorAnalysisDimension(
                dimension="卖点表达",
                competitor_pattern="演示假设：高信息密度素材只突出一至三个核心卖点",
                own_product_gap=pending,
                recommendation="将可验证属性压缩为三个短句，避免绝对化功效承诺",
                confidence=0.35,
            ),
            CompetitorAnalysisDimension(
                dimension="品牌差异化",
                competitor_pattern="演示假设：竞品容易出现模板化构图和相似文案",
                own_product_gap=pending,
                recommendation="保留品类识别度，同时用品牌色和独特场景建立差异",
                confidence=0.35,
            ),
        ]
        briefs = [
            DifferentiatedCreativeBrief(
                name="高识别主图方案",
                visual_direction="干净背景、准确商品颜色、突出轮廓",
                composition="商品居中并保留平台安全边距",
                copy_angle="一个核心卖点加两个可验证属性",
                differentiation="使用品牌色小面积点缀，避免复制竞品装饰元素",
            ),
            DifferentiatedCreativeBrief(
                name="真实场景方案",
                visual_direction=f"面向{product.target_audience}的真实使用环境",
                composition="人物与商品形成明确视觉主次",
                copy_angle="使用场景、材质体验和适用人群",
                differentiation="用真实情境代替竞品常见的纯棚拍表达",
            ),
            DifferentiatedCreativeBrief(
                name="卖点海报方案",
                visual_direction="低信息噪声、模块化卖点、适配移动端",
                composition="商品占左侧或中心，右侧保留可编辑文案区",
                copy_angle="短标题、三项卖点和明确行动引导",
                differentiation="重新组织信息层级，不复刻竞品文字和版式",
            ),
        ]
        return CompetitorPluginResult(
            plugin_id=self.descriptor.plugin_id,
            summary=(
                f"已为 {product.name} 建立包含 {count} 张竞品图的 Mock 对标报告。"
                "当前结果用于验证业务结构，未真实读取图片像素。"
            ),
            dimensions=dimensions,
            opportunities=[
                "建立统一商品身份约束，避免多张生成图出现颜色和版型漂移",
                "同时生成主图、场景图和卖点海报，用后续点击数据验证效果",
                "所有差异化方案保留来源记录，不直接复制竞品图片和文案",
            ],
            creative_briefs=briefs,
            trace=[
                "validate_competitor_inputs",
                "declare_mock_vision_boundary",
                "build_comparison_dimensions",
                "generate_differentiated_briefs",
                "apply_non_copying_policy",
            ],
            mock=True,
        )
