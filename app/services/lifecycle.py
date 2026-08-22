import hashlib
from functools import lru_cache
from uuid import UUID

from app.domain.models import (
    ApprovalDecisionRequest,
    AuditEvent,
    CampaignLifecycle,
    CampaignPackage,
    CampaignRevisionRequest,
    CampaignVersion,
    LifecycleStatus,
    Platform,
    PlatformCopy,
    PlatformPublicationResult,
    PublishBatchResult,
    PublishRequest,
)
from app.services.idempotency import IdempotencyStore, get_idempotency_store
from app.services.persistence import JsonStateStore, get_state_store


class LifecycleNotFoundError(Exception):
    pass


class LifecycleConflictError(Exception):
    pass


class PlatformPublishError(Exception):
    pass


class PlatformPublisher:
    def publish(
        self,
        campaign_id: UUID,
        version: int,
        copy: PlatformCopy,
        idempotency_key: str,
    ) -> PlatformPublicationResult:
        raise NotImplementedError


class MockPlatformPublisher(PlatformPublisher):
    """Deterministic adapter used until an official platform credential is configured."""

    def publish(
        self,
        campaign_id: UUID,
        version: int,
        copy: PlatformCopy,
        idempotency_key: str,
    ) -> PlatformPublicationResult:
        raw = f"{campaign_id}:{version}:{copy.platform}:{idempotency_key}"
        external_id = hashlib.sha256(raw.encode()).hexdigest()[:20]
        return PlatformPublicationResult(
            platform=copy.platform,
            status="published",
            external_id=f"mock-{copy.platform.value}-{external_id}",
        )


class CampaignLifecycleService:
    def __init__(
        self,
        publishers: dict[Platform, PlatformPublisher] | None = None,
        state_store: JsonStateStore | None = None,
        idempotency_store: IdempotencyStore | None = None,
    ) -> None:
        self._campaigns: dict[UUID, CampaignLifecycle] = {}
        self.state_store = state_store or get_state_store()
        self.idempotency_store = idempotency_store or get_idempotency_store()
        self.publishers = publishers or {
            platform: MockPlatformPublisher() for platform in Platform
        }

    def _save(self, lifecycle: CampaignLifecycle) -> None:
        self.state_store.put(
            "campaign_lifecycle",
            str(lifecycle.campaign_id),
            lifecycle.model_dump(mode="json"),
        )

    def create_draft(self, package: CampaignPackage, actor: str) -> CampaignLifecycle:
        existing = self._campaigns.get(package.campaign_id)
        if existing:
            return existing
        version = CampaignVersion(
            version=1,
            copies=package.copies,
            poster_prompt=package.poster_prompt,
            created_by=actor,
            change_note="initial generated content",
        )
        lifecycle = CampaignLifecycle(
            campaign_id=package.campaign_id,
            status=LifecycleStatus.DRAFT,
            current_version=1,
            versions=[version],
            audit_log=[
                AuditEvent(
                    actor=actor,
                    action="draft_created",
                    details={"version": "1", "quality_score": str(package.quality_score)},
                )
            ],
        )
        self._campaigns[package.campaign_id] = lifecycle
        self._save(lifecycle)
        return lifecycle

    def get(self, campaign_id: UUID) -> CampaignLifecycle:
        lifecycle = self._campaigns.get(campaign_id)
        if not lifecycle:
            payload = self.state_store.get("campaign_lifecycle", str(campaign_id))
            if payload:
                lifecycle = CampaignLifecycle.model_validate(payload)
                self._campaigns[campaign_id] = lifecycle
        if not lifecycle:
            raise LifecycleNotFoundError("campaign lifecycle not found")
        return lifecycle

    def revise(
        self, campaign_id: UUID, request: CampaignRevisionRequest
    ) -> CampaignLifecycle:
        lifecycle = self.get(campaign_id)
        if lifecycle.status not in {LifecycleStatus.DRAFT, LifecycleStatus.REJECTED}:
            raise LifecycleConflictError("only draft or rejected campaigns can be revised")
        current = lifecycle.versions[-1]
        next_version = current.version + 1
        lifecycle.versions.append(
            CampaignVersion(
                version=next_version,
                copies=request.copies if request.copies is not None else current.copies,
                poster_prompt=(
                    request.poster_prompt
                    if request.poster_prompt is not None
                    else current.poster_prompt
                ),
                created_by=request.actor,
                change_note=request.change_note,
            )
        )
        lifecycle.current_version = next_version
        lifecycle.status = LifecycleStatus.DRAFT
        lifecycle.requested_by = None
        lifecycle.reviewed_by = None
        lifecycle.review_reason = None
        lifecycle.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action="version_created",
                details={"version": str(next_version), "note": request.change_note},
            )
        )
        self._save(lifecycle)
        return lifecycle

    def submit_review(self, campaign_id: UUID, actor: str) -> CampaignLifecycle:
        lifecycle = self.get(campaign_id)
        if lifecycle.status != LifecycleStatus.DRAFT:
            raise LifecycleConflictError("only draft campaigns can be submitted for review")
        lifecycle.status = LifecycleStatus.PENDING_REVIEW
        lifecycle.requested_by = actor
        lifecycle.audit_log.append(
            AuditEvent(
                actor=actor,
                action="review_submitted",
                details={"version": str(lifecycle.current_version)},
            )
        )
        self._save(lifecycle)
        return lifecycle

    def decide(
        self, campaign_id: UUID, request: ApprovalDecisionRequest
    ) -> CampaignLifecycle:
        lifecycle = self.get(campaign_id)
        if lifecycle.status != LifecycleStatus.PENDING_REVIEW:
            raise LifecycleConflictError("campaign is not pending review")
        if lifecycle.requested_by == request.reviewer:
            raise LifecycleConflictError("reviewer must differ from the submitter")
        lifecycle.reviewed_by = request.reviewer
        lifecycle.review_reason = request.reason
        lifecycle.status = (
            LifecycleStatus.APPROVED
            if request.action == "approve"
            else LifecycleStatus.REJECTED
        )
        lifecycle.audit_log.append(
            AuditEvent(
                actor=request.reviewer,
                action=(
                    "review_approved"
                    if request.action == "approve"
                    else "review_rejected"
                ),
                details={
                    "version": str(lifecycle.current_version),
                    "reason": request.reason or "",
                },
            )
        )
        self._save(lifecycle)
        return lifecycle

    def publish(self, campaign_id: UUID, request: PublishRequest) -> PublishBatchResult:
        lifecycle = self.get(campaign_id)
        cached_entry = self.idempotency_store.get(request.idempotency_key)
        current_owner = (campaign_id, lifecycle.current_version)
        if cached_entry:
            owner = (cached_entry[0], cached_entry[1])
            if owner != current_owner:
                raise LifecycleConflictError(
                    "idempotency key is already used by another version"
                )
            return cached_entry[2]
        if lifecycle.status != LifecycleStatus.APPROVED:
            raise LifecycleConflictError("only approved campaigns can be published")

        version = lifecycle.versions[-1]
        copies = {copy.platform: copy for copy in version.copies}
        missing = [platform.value for platform in request.platforms if platform not in copies]
        if missing:
            raise LifecycleConflictError(
                f"approved version has no content for platforms: {', '.join(missing)}"
            )
        results: list[PlatformPublicationResult] = []
        for platform in request.platforms:
            publisher = self.publishers[platform]
            try:
                results.append(
                    publisher.publish(
                        campaign_id,
                        lifecycle.current_version,
                        copies[platform],
                        request.idempotency_key,
                    )
                )
            except PlatformPublishError as exc:  # isolate one destination from the batch
                results.append(
                    PlatformPublicationResult(
                        platform=platform, status="failed", error=str(exc)
                    )
                )
        final_status = (
            LifecycleStatus.PUBLISHED
            if all(item.status == "published" for item in results)
            else LifecycleStatus.PARTIAL_FAILED
        )
        lifecycle.status = final_status
        lifecycle.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action="publish_completed",
                details={
                    "version": str(lifecycle.current_version),
                    "idempotency_key": request.idempotency_key,
                    "status": final_status.value,
                },
            )
        )
        batch = PublishBatchResult(
            campaign_id=campaign_id,
            version=lifecycle.current_version,
            idempotency_key=request.idempotency_key,
            status=final_status,
            results=results,
        )
        self.idempotency_store.put(
            request.idempotency_key,
            campaign_id,
            lifecycle.current_version,
            batch,
        )
        self._save(lifecycle)
        return batch


@lru_cache
def get_lifecycle_service() -> CampaignLifecycleService:
    return CampaignLifecycleService()
