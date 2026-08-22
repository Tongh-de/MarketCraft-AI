from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from app.domain.creation import (
    CompetitorAnalysisReport,
    CompetitorAnalysisRequest,
    CreationTaskStatus,
)
from app.plugins.base import CreativePluginError
from app.plugins.registry import CreativePluginRegistry, get_creative_plugin_registry
from app.services.persistence import JsonStateStore, get_state_store
from app.skills.base import SkillNotFoundError
from app.skills.registry import SkillRegistry, get_skill_registry


class CompetitorReportNotFoundError(Exception):
    pass


class CompetitorAnalysisService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        skill_registry: SkillRegistry | None = None,
        plugin_registry: CreativePluginRegistry | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.skill_registry = skill_registry or get_skill_registry()
        self.plugin_registry = plugin_registry or get_creative_plugin_registry()

    def _save(self, report: CompetitorAnalysisReport) -> None:
        self.state_store.put(
            "competitor_analysis_report",
            str(report.report_id),
            report.model_dump(mode="json"),
        )

    def create(self, request: CompetitorAnalysisRequest) -> CompetitorAnalysisReport:
        report = CompetitorAnalysisReport(
            status=CreationTaskStatus.RUNNING,
            product=request.product,
            competitor_images=request.competitor_images,
            instruction=request.instruction,
            requested_by=request.actor,
            compliance_notes=[
                "只提取通用视觉规律，不复制竞品图片、商标、文案或独特版式。",
                "Mock 报告未真实读取图片像素，结论不能作为实际投放依据。",
            ],
            trace=["report_created", "select_skill:competitor-visual-analysis"],
        )
        self._save(report)
        try:
            skill = self.skill_registry.get("competitor-visual-analysis")
            result = skill.execute(request, self.plugin_registry)
        except (SkillNotFoundError, CreativePluginError, RuntimeError, ValueError) as error:
            report.status = CreationTaskStatus.FAILED
            report.error = str(error)
            report.trace.append("report_failed")
            self._save(report)
            return report

        report.plugin_id = result.plugin_id
        report.summary = result.summary
        report.dimensions = result.dimensions
        report.opportunities = result.opportunities
        report.creative_briefs = result.creative_briefs
        report.trace.extend(result.trace)
        report.trace.append("report_completed")
        report.mock = result.mock
        report.status = CreationTaskStatus.COMPLETED
        report.completed_at = datetime.now(UTC)
        self._save(report)
        return report

    def get(self, report_id: UUID) -> CompetitorAnalysisReport:
        payload = self.state_store.get("competitor_analysis_report", str(report_id))
        if not payload:
            raise CompetitorReportNotFoundError("competitor analysis report not found")
        return CompetitorAnalysisReport.model_validate(payload)

    def list_reports(self, limit: int = 50) -> list[CompetitorAnalysisReport]:
        reports = [
            CompetitorAnalysisReport.model_validate(payload)
            for payload in self.state_store.list("competitor_analysis_report")
        ]
        return sorted(reports, key=lambda report: report.created_at, reverse=True)[:limit]


@lru_cache
def get_competitor_analysis_service() -> CompetitorAnalysisService:
    return CompetitorAnalysisService()
