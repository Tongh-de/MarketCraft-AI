from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from app.domain.creation import CreationTaskStatus
from app.domain.listings import (
    ListingDecisionRequest,
    ListingPackageRequest,
    ListingPlatform,
    ListingPublicationResult,
    ListingPublishBatchResult,
    ListingPublishRequest,
    ListingStatus,
    ProductListingPackage,
)
from app.domain.models import AuditEvent
from app.plugins.listing_publishers import ListingPublishError, MockListingPublisher
from app.services.creation_tasks import (
    CreationTaskNotFoundError,
    CreationTaskService,
    get_creation_task_service,
)
from app.services.persistence import JsonStateStore, get_state_store
from app.services.poster_projects import (
    PosterProjectNotFoundError,
    PosterProjectService,
    get_poster_project_service,
)
from app.skills.registry import SkillRegistry, get_skill_registry
from app.telemetry import traced


class ListingPackageNotFoundError(Exception):
    pass


class ListingPackageConflictError(Exception):
    pass


class ListingPackageService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        creation_service: CreationTaskService | None = None,
        poster_service: PosterProjectService | None = None,
        skill_registry: SkillRegistry | None = None,
        publishers: dict[ListingPlatform, MockListingPublisher] | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.creation_service = creation_service or get_creation_task_service()
        self.poster_service = poster_service or get_poster_project_service()
        self.skill_registry = skill_registry or get_skill_registry()
        self.publishers = publishers or {
            platform: MockListingPublisher(platform) for platform in ListingPlatform
        }

    def _save(self, package: ProductListingPackage) -> None:
        package.updated_at = datetime.now(UTC)
        self.state_store.put(
            "listing_package", str(package.package_id), package.model_dump(mode="json")
        )

    @traced("listing.package.create")
    def create(self, request: ListingPackageRequest) -> ProductListingPackage:
        try:
            creation_task = self.creation_service.get(request.creation_task_id)
        except CreationTaskNotFoundError as error:
            raise ListingPackageNotFoundError(str(error)) from error
        if creation_task.status != CreationTaskStatus.COMPLETED:
            raise ListingPackageConflictError("creation task must be completed")
        if creation_task.product.sku != request.product.sku:
            raise ListingPackageConflictError("creation task SKU must match listing SKU")

        poster_project = None
        if request.poster_project_id:
            try:
                poster_project = self.poster_service.get(request.poster_project_id)
            except PosterProjectNotFoundError as error:
                raise ListingPackageNotFoundError(str(error)) from error
            if poster_project.product.sku != request.product.sku:
                raise ListingPackageConflictError("poster project SKU must match listing SKU")

        skill = self.skill_registry.get("product-listing-package")
        result, assets = skill.execute(request, creation_task, poster_project)
        package = ProductListingPackage(
            creation_task_id=request.creation_task_id,
            poster_project_id=request.poster_project_id,
            product=request.product,
            platforms=request.platforms,
            assets=assets,
            drafts=result.drafts,
            requested_by=request.actor,
            trace=result.trace,
            audit_log=[
                AuditEvent(
                    actor=request.actor,
                    action="listing_package_created",
                    details={
                        "platforms": ",".join(item.value for item in request.platforms),
                        "asset_count": str(len(assets)),
                    },
                )
            ],
        )
        self._save(package)
        return package

    def get(self, package_id: UUID) -> ProductListingPackage:
        payload = self.state_store.get("listing_package", str(package_id))
        if not payload:
            raise ListingPackageNotFoundError("listing package not found")
        return ProductListingPackage.model_validate(payload)

    def list_packages(self, limit: int = 50) -> list[ProductListingPackage]:
        packages = [
            ProductListingPackage.model_validate(payload)
            for payload in self.state_store.list("listing_package")
        ]
        return sorted(packages, key=lambda item: item.updated_at, reverse=True)[:limit]

    @traced("listing.package.submit_review")
    def submit_review(self, package_id: UUID, actor: str) -> ProductListingPackage:
        package = self.get(package_id)
        if package.status != ListingStatus.DRAFT:
            raise ListingPackageConflictError("only draft listing packages can be reviewed")
        package.status = ListingStatus.PENDING_REVIEW
        package.requested_by = actor
        package.audit_log.append(
            AuditEvent(actor=actor, action="listing_review_submitted")
        )
        self._save(package)
        return package

    @traced("listing.package.decide")
    def decide(
        self, package_id: UUID, request: ListingDecisionRequest
    ) -> ProductListingPackage:
        package = self.get(package_id)
        if package.status != ListingStatus.PENDING_REVIEW:
            raise ListingPackageConflictError("listing package is not pending review")
        if package.requested_by == request.reviewer:
            raise ListingPackageConflictError("reviewer must differ from the submitter")
        package.reviewed_by = request.reviewer
        package.review_reason = request.reason
        package.status = (
            ListingStatus.APPROVED
            if request.action == "approve"
            else ListingStatus.REJECTED
        )
        package.audit_log.append(
            AuditEvent(
                actor=request.reviewer,
                action=(
                    "listing_review_approved"
                    if request.action == "approve"
                    else "listing_review_rejected"
                ),
                details={"reason": request.reason or ""},
            )
        )
        self._save(package)
        return package

    @traced("listing.package.publish")
    def publish(
        self, package_id: UUID, request: ListingPublishRequest
    ) -> ListingPublishBatchResult:
        package = self.get(package_id)
        cached = self.state_store.get(
            "listing_publish_idempotency", request.idempotency_key
        )
        if cached:
            if cached["package_id"] != str(package_id) or cached["version"] != package.version:
                raise ListingPackageConflictError(
                    "idempotency key is already used by another listing package"
                )
            return ListingPublishBatchResult.model_validate(cached["result"])
        if package.status != ListingStatus.APPROVED:
            raise ListingPackageConflictError("only approved listing packages can be published")

        results: list[ListingPublicationResult] = []
        for draft in package.drafts:
            try:
                results.append(
                    self.publishers[draft.platform].publish(
                        package, draft, request.idempotency_key
                    )
                )
            except ListingPublishError as error:
                results.append(
                    ListingPublicationResult(
                        platform=draft.platform,
                        status="failed",
                        error=str(error),
                        mock=True,
                    )
                )
        package.publication_results = results
        package.status = (
            ListingStatus.PUBLISHED
            if all(item.status == "published" for item in results)
            else ListingStatus.PARTIAL_FAILED
        )
        package.trace.append("publish_approved_listing_package")
        package.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action="listing_publish_completed",
                details={
                    "idempotency_key": request.idempotency_key,
                    "status": package.status.value,
                },
            )
        )
        batch = ListingPublishBatchResult(
            package_id=package_id,
            version=package.version,
            idempotency_key=request.idempotency_key,
            status=package.status,
            results=results,
        )
        self.state_store.put(
            "listing_publish_idempotency",
            request.idempotency_key,
            {
                "package_id": str(package_id),
                "version": package.version,
                "result": batch.model_dump(mode="json"),
            },
        )
        self._save(package)
        return batch


@lru_cache
def get_listing_package_service() -> ListingPackageService:
    return ListingPackageService()
