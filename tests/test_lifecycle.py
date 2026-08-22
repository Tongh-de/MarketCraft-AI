from uuid import uuid4

import pytest

from app.domain.models import (
    ApprovalDecisionRequest,
    CampaignRequest,
    CampaignRevisionRequest,
    ProductInput,
    PublishRequest,
)
from app.services.lifecycle import (
    CampaignLifecycleService,
    LifecycleConflictError,
    PlatformPublisher,
    PlatformPublishError,
)
from app.workflows.campaign import run_campaign


def make_package():
    request = CampaignRequest(
        product=ProductInput(
            sku="FLOW-CUP-001",
            name="审批测试保温杯",
            category="咖啡杯",
            description="用于验证内容审批、版本和发布流程的保温杯。",
            attributes={"容量": "450ml"},
            target_audience="通勤用户",
        )
    )
    return run_campaign(request, f"lifecycle-{uuid4()}")


def test_four_eyes_approval_and_idempotent_publish() -> None:
    service = CampaignLifecycleService()
    package = make_package()
    lifecycle = service.create_draft(package, "content-agent")
    service.submit_review(package.campaign_id, "operator-a")

    with pytest.raises(LifecycleConflictError, match="reviewer must differ"):
        service.decide(
            package.campaign_id,
            ApprovalDecisionRequest(reviewer="operator-a", action="approve"),
        )

    approved = service.decide(
        package.campaign_id,
        ApprovalDecisionRequest(reviewer="reviewer-b", action="approve"),
    )
    request = PublishRequest(
        actor="publisher-c",
        idempotency_key="publish-flow-cup-001",
        platforms=["xiaohongshu", "douyin"],
    )
    first = service.publish(package.campaign_id, request)
    retried = service.publish(package.campaign_id, request)

    assert lifecycle.current_version == 1
    assert approved.status == "published"
    assert first == retried
    assert all(result.external_id.startswith("mock-") for result in first.results)
    assert [event.action for event in approved.audit_log].count("publish_completed") == 1


def test_rejected_campaign_revision_creates_new_version() -> None:
    service = CampaignLifecycleService()
    package = make_package()
    service.create_draft(package, "content-agent")
    service.submit_review(package.campaign_id, "operator-a")
    rejected = service.decide(
        package.campaign_id,
        ApprovalDecisionRequest(
            reviewer="reviewer-b", action="reject", reason="行动引导需要更克制"
        ),
    )
    revised = service.revise(
        package.campaign_id,
        CampaignRevisionRequest(
            actor="operator-a",
            change_note="调整海报布局和行动引导",
            poster_prompt=package.poster_prompt + " Use a softer call-to-action area.",
        ),
    )
    assert rejected.current_version == 2
    assert revised.status == "draft"
    assert revised.current_version == 2
    assert revised.requested_by is None


def test_unapproved_campaign_cannot_publish() -> None:
    service = CampaignLifecycleService()
    package = make_package()
    service.create_draft(package, "content-agent")
    with pytest.raises(LifecycleConflictError, match="only approved"):
        service.publish(
            package.campaign_id,
            PublishRequest(
                actor="publisher-c",
                idempotency_key="unapproved-flow-001",
                platforms=["xiaohongshu"],
            ),
        )


def test_platform_failure_is_reported_without_fake_success() -> None:
    class FailingPublisher(PlatformPublisher):
        def publish(self, campaign_id, version, copy, idempotency_key):
            raise PlatformPublishError("platform credential rejected")

    service = CampaignLifecycleService(publishers={"xiaohongshu": FailingPublisher()})
    package = make_package()
    service.create_draft(package, "content-agent")
    service.submit_review(package.campaign_id, "operator-a")
    service.decide(
        package.campaign_id,
        ApprovalDecisionRequest(reviewer="reviewer-b", action="approve"),
    )
    result = service.publish(
        package.campaign_id,
        PublishRequest(
            actor="publisher-c",
            idempotency_key="failing-platform-001",
            platforms=["xiaohongshu"],
        ),
    )
    assert result.status == "partial_failed"
    assert result.results[0].status == "failed"
    assert result.results[0].external_id is None
