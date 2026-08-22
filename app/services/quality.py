import re

from app.domain.models import CampaignRequest, PlatformCopy, QualityIssue


ABSOLUTE_CLAIMS = ("第一", "最好", "顶级", "百分百", "永久", "绝对")


class QualityService:
    def review(
        self, request: CampaignRequest, copies: list[PlatformCopy]
    ) -> tuple[int, list[QualityIssue]]:
        issues: list[QualityIssue] = []
        source = " ".join(f"{copy.title} {copy.body}" for copy in copies)

        for claim in (*ABSOLUTE_CLAIMS, *request.forbidden_claims):
            if claim and claim in source:
                issues.append(
                    QualityIssue(
                        severity="high",
                        rule="prohibited_claim",
                        message=f"文案包含禁用或高风险表述：{claim}",
                    )
                )

        for copy in copies:
            if len(copy.title) > 60:
                issues.append(
                    QualityIssue(
                        severity="medium",
                        rule="title_length",
                        message=f"{copy.platform.value} 标题超过 60 个字符",
                    )
                )
            if not re.search(r"[。！？.!?]", copy.body):
                issues.append(
                    QualityIssue(
                        severity="low",
                        rule="readability",
                        message=f"{copy.platform.value} 正文缺少清晰断句",
                    )
                )

        deduction = sum({"high": 25, "medium": 10, "low": 5}[x.severity] for x in issues)
        return max(0, 100 - deduction), issues

