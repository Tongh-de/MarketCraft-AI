import hashlib

from app.domain.listings import (
    ListingPlatform,
    ListingPublicationResult,
    PlatformListingDraft,
    ProductListingPackage,
)


class ListingPublishError(Exception):
    pass


class MockListingPublisher:
    def __init__(self, platform: ListingPlatform) -> None:
        self.platform = platform

    def publish(
        self,
        package: ProductListingPackage,
        draft: PlatformListingDraft,
        idempotency_key: str,
    ) -> ListingPublicationResult:
        raw = f"{package.package_id}:{package.version}:{draft.platform}:{idempotency_key}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:20]
        return ListingPublicationResult(
            platform=self.platform,
            status="published",
            external_id=f"mock-{self.platform.value}-listing-{digest}",
            mock=True,
        )
