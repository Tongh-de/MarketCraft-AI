from app.domain.creation import SkillDescriptor
from app.domain.listings import ProductListingPackage
from app.domain.performance import (
    OptimizationCategory,
    OptimizationPriority,
    OptimizationRecommendation,
    PerformanceAnalysisReport,
    PerformanceSnapshot,
    PlatformPerformanceSummary,
)


class CommercePerformanceOptimizationSkill:
    descriptor = SkillDescriptor(
        skill_id="commerce-performance-optimization",
        name="电商经营优化 Skill",
        description="分析曝光、点击、转化、广告、退货和库存数据，生成可追溯优化建议。",
        version="1.0.0",
        required_capabilities=[],
    )

    def execute(
        self,
        package: ProductListingPackage,
        snapshots: list[PerformanceSnapshot],
        actor: str,
    ) -> PerformanceAnalysisReport:
        summaries = [self._summary(snapshot) for snapshot in snapshots]
        recommendations: list[OptimizationRecommendation] = []
        for snapshot in snapshots:
            recommendations.extend(self._platform_recommendations(snapshot))
        findings = self._cross_platform_findings(summaries)
        recommendations.extend(self._growth_recommendations(summaries))
        ordered = sorted(
            recommendations,
            key=lambda item: {
                OptimizationPriority.HIGH: 0,
                OptimizationPriority.MEDIUM: 1,
                OptimizationPriority.LOW: 2,
            }[item.priority],
        )
        high_count = sum(item.priority == OptimizationPriority.HIGH for item in ordered)
        headline = (
            f"已分析 {len(summaries)} 个平台，识别 {high_count} 项高优先级优化机会。"
            if high_count
            else f"已分析 {len(summaries)} 个平台，当前指标稳定，可进入小流量增量测试。"
        )
        return PerformanceAnalysisReport(
            package_id=package.package_id,
            sku=package.product.sku,
            product_name=package.product.name,
            snapshot_ids=[item.snapshot_id for item in snapshots],
            summaries=summaries,
            headline=headline,
            cross_platform_findings=findings,
            recommendations=ordered,
            data_quality_notes=[
                "当前数据由 Mock 平台连接器或手工演示数据提供，不代表真实经营结果。",
                "建议至少积累 7 至 14 天同口径数据后，再将建议用于真实业务决策。",
                "归因窗口、退款延迟和平台口径差异需在接入真实 API 时单独校准。",
            ],
            trace=[
                "load_latest_platform_snapshots",
                "validate_metric_funnels",
                "calculate_derived_metrics",
                "compare_platform_benchmarks",
                "detect_inventory_and_return_risks",
                "generate_evidence_backed_recommendations",
                "mark_actions_for_human_review",
            ],
            requested_by=actor,
            mock=True,
        )

    @staticmethod
    def _summary(snapshot: PerformanceSnapshot) -> PlatformPerformanceSummary:
        return PlatformPerformanceSummary(
            platform=snapshot.platform,
            impressions=snapshot.impressions,
            clicks=snapshot.clicks,
            orders=snapshot.orders,
            units_sold=snapshot.units_sold,
            revenue=snapshot.revenue,
            inventory=snapshot.inventory,
            ctr=snapshot.ctr,
            conversion_rate=snapshot.conversion_rate,
            roas=snapshot.roas,
            return_rate=snapshot.return_rate,
        )

    def _platform_recommendations(
        self, snapshot: PerformanceSnapshot
    ) -> list[OptimizationRecommendation]:
        platform = snapshot.platform
        label = platform.value
        recommendations: list[OptimizationRecommendation] = []
        if snapshot.ctr < 1.5:
            recommendations.append(
                OptimizationRecommendation(
                    platform=platform,
                    category=OptimizationCategory.CREATIVE,
                    priority=OptimizationPriority.HIGH,
                    title=f"提升 {label} 首图与标题点击力",
                    diagnosis="曝光已形成但点击率偏低，当前首图或标题没有充分传递核心卖点。",
                    evidence=[
                        f"CTR {snapshot.ctr:.2f}%",
                        "MVP 观察基准 1.50%",
                        f"{snapshot.impressions} 次曝光仅带来 {snapshot.clicks} 次点击",
                    ],
                    suggested_actions=[
                        "用模特试穿图与纯商品图各制作一个版本",
                        "将材质或使用场景卖点前置到标题前半段",
                        "采用小流量 A/B 测试，保留原版本作为对照组",
                    ],
                    target_metric="CTR",
                )
            )
        if snapshot.conversion_rate < 3.0:
            recommendations.append(
                OptimizationRecommendation(
                    platform=platform,
                    category=OptimizationCategory.CONVERSION,
                    priority=OptimizationPriority.HIGH,
                    title=f"修复 {label} 详情页转化断点",
                    diagnosis="用户进入详情页后下单比例偏低，需要优先核对内容可信度与价格表达。",
                    evidence=[
                        f"点击到订单转化率 {snapshot.conversion_rate:.2f}%",
                        "MVP 观察基准 3.00%",
                        f"{snapshot.clicks} 次点击形成 {snapshot.orders} 笔订单",
                    ],
                    suggested_actions=[
                        "补充尺寸、材质细节与真实使用场景信息",
                        "检查价格、运费和交付时效是否在首屏清晰可见",
                        "保持商品属性与图片一致，避免生成内容过度承诺",
                    ],
                    target_metric="Conversion Rate",
                )
            )
        if snapshot.ad_spend > 0 and snapshot.roas < 2.5:
            recommendations.append(
                OptimizationRecommendation(
                    platform=platform,
                    category=OptimizationCategory.ADVERTISING,
                    priority=OptimizationPriority.MEDIUM,
                    title=f"收紧 {label} 低效投放",
                    diagnosis="广告投入产出低于观察基准，继续放量会扩大低效流量成本。",
                    evidence=[
                        f"ROAS {snapshot.roas:.2f}",
                        "MVP 观察基准 2.50",
                        f"广告消耗 {snapshot.ad_spend:.2f}，收入 {snapshot.revenue:.2f}",
                    ],
                    suggested_actions=[
                        "拆分自然流量与广告流量后再判断素材质量",
                        "暂停高消耗低转化词，保留高意图词进行验证",
                    ],
                    target_metric="ROAS",
                )
            )
        if snapshot.return_rate > 8.0:
            recommendations.append(
                OptimizationRecommendation(
                    platform=platform,
                    category=OptimizationCategory.CUSTOMER_EXPERIENCE,
                    priority=OptimizationPriority.HIGH,
                    title=f"降低 {label} 退货预期差",
                    diagnosis="退货率偏高，商品描述、图片表现或尺码信息可能与实际体验存在偏差。",
                    evidence=[
                        f"退货率 {snapshot.return_rate:.2f}%",
                        "MVP 观察基准 8.00%",
                    ],
                    suggested_actions=[
                        "核对模特图与商品实物的颜色、版型和材质一致性",
                        "在详情页增加尺码建议和非理想使用场景说明",
                    ],
                    target_metric="Return Rate",
                )
            )
        days = max((snapshot.period_end - snapshot.period_start).days + 1, 1)
        daily_sales = snapshot.units_sold / days
        coverage = snapshot.inventory / daily_sales if daily_sales else 999.0
        if coverage < 14:
            recommendations.append(
                OptimizationRecommendation(
                    platform=platform,
                    category=OptimizationCategory.INVENTORY,
                    priority=OptimizationPriority.HIGH,
                    title=f"关注 {label} 库存覆盖风险",
                    diagnosis="按当前销售速度估算，库存覆盖天数低于安全观察线。",
                    evidence=[
                        f"库存覆盖约 {coverage:.1f} 天",
                        f"当前库存 {snapshot.inventory}，周期销量 {snapshot.units_sold}",
                    ],
                    suggested_actions=[
                        "提交补货评估，并由运营人员复核供应周期",
                        "在补货确认前避免直接扩大投放预算",
                    ],
                    target_metric="Inventory Coverage Days",
                )
            )
        return recommendations

    @staticmethod
    def _cross_platform_findings(
        summaries: list[PlatformPerformanceSummary],
    ) -> list[str]:
        if not summaries:
            return []
        best_ctr = max(summaries, key=lambda item: item.ctr)
        best_conversion = max(summaries, key=lambda item: item.conversion_rate)
        best_roas = max(summaries, key=lambda item: item.roas)
        return [
            f"{best_ctr.platform.value} 的 CTR 最高，为 {best_ctr.ctr:.2f}% 。",
            (
                f"{best_conversion.platform.value} 的点击到订单转化率最高，"
                f"为 {best_conversion.conversion_rate:.2f}% 。"
            ),
            f"{best_roas.platform.value} 的 ROAS 最高，为 {best_roas.roas:.2f} 。",
        ]

    @staticmethod
    def _growth_recommendations(
        summaries: list[PlatformPerformanceSummary],
    ) -> list[OptimizationRecommendation]:
        if len(summaries) < 2:
            return []
        winner = max(summaries, key=lambda item: item.ctr + item.conversion_rate)
        return [
            OptimizationRecommendation(
                platform=None,
                category=OptimizationCategory.GROWTH,
                priority=OptimizationPriority.LOW,
                title="复用胜出平台的创意假设",
                diagnosis=(
                    f"{winner.platform.value} 的点击与转化组合表现相对更好，"
                    "可以提炼其创意假设，而不是直接复制素材。"
                ),
                evidence=[
                    f"CTR {winner.ctr:.2f}%",
                    f"转化率 {winner.conversion_rate:.2f}%",
                ],
                suggested_actions=[
                    "提取胜出版本的卖点顺序、构图和场景变量",
                    "为其他平台重新适配尺寸与表达，再进行独立 A/B 测试",
                ],
                target_metric="Cross-platform Lift",
            )
        ]
