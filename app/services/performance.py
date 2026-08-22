from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

from app.domain.listings import ListingPlatform, ListingStatus, ProductListingPackage
from app.domain.performance import (
    PerformanceAnalysisReport,
    PerformanceSnapshot,
    PerformanceSnapshotRequest,
    PerformanceSource,
)
from app.services.listing_packages import (
    ListingPackageNotFoundError,
    ListingPackageService,
    get_listing_package_service,
)
from app.services.persistence import JsonStateStore, get_state_store
from app.skills.registry import SkillRegistry, get_skill_registry


class PerformanceNotFoundError(Exception):
    pass


class PerformanceConflictError(Exception):
    pass


class CommercePerformanceService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        listing_service: ListingPackageService | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.listing_service = listing_service or get_listing_package_service()
        self.skill_registry = skill_registry or get_skill_registry()

    def _get_published_package(self, package_id: UUID) -> ProductListingPackage:
        try:
            package = self.listing_service.get(package_id)
        except ListingPackageNotFoundError as error:
            raise PerformanceNotFoundError(str(error)) from error
        if package.status != ListingStatus.PUBLISHED:
            raise PerformanceConflictError(
                "performance data requires a published listing package"
            )
        return package

    @staticmethod
    def _safe_rate(numerator: float, denominator: float) -> float:
        return round(numerator / denominator * 100, 2) if denominator else 0.0

    @staticmethod
    def _external_listing_id(
        package: ProductListingPackage, platform: ListingPlatform
    ) -> str:
        result = next(
            (
                item
                for item in package.publication_results
                if item.platform == platform and item.external_id
            ),
            None,
        )
        if not result or not result.external_id:
            raise PerformanceConflictError(
                f"published listing ID is missing for platform: {platform.value}"
            )
        return result.external_id

    def create_snapshot(
        self, request: PerformanceSnapshotRequest
    ) -> PerformanceSnapshot:
        package = self._get_published_package(request.package_id)
        if request.platform not in package.platforms:
            raise PerformanceConflictError(
                "snapshot platform is not included in the listing package"
            )
        snapshot = PerformanceSnapshot(
            package_id=request.package_id,
            sku=package.product.sku,
            platform=request.platform,
            external_listing_id=self._external_listing_id(package, request.platform),
            period_start=request.period_start,
            period_end=request.period_end,
            impressions=request.impressions,
            clicks=request.clicks,
            add_to_carts=request.add_to_carts,
            orders=request.orders,
            units_sold=request.units_sold,
            revenue=round(request.revenue, 2),
            ad_spend=round(request.ad_spend, 2),
            returns=request.returns,
            inventory=request.inventory,
            ctr=self._safe_rate(request.clicks, request.impressions),
            add_to_cart_rate=self._safe_rate(request.add_to_carts, request.clicks),
            conversion_rate=self._safe_rate(request.orders, request.clicks),
            roas=(
                round(request.revenue / request.ad_spend, 2)
                if request.ad_spend
                else 0.0
            ),
            return_rate=self._safe_rate(request.returns, request.units_sold),
            source=request.source,
            captured_by=request.actor,
            mock=True,
        )
        self.state_store.put(
            "performance_snapshot",
            str(snapshot.snapshot_id),
            snapshot.model_dump(mode="json"),
        )
        return snapshot

    def create_demo_snapshots(
        self, package_id: UUID, actor: str
    ) -> list[PerformanceSnapshot]:
        package = self._get_published_package(package_id)
        end = datetime.now(UTC).date()
        start = end - timedelta(days=6)
        price = package.product.price
        demo_metrics = {
            ListingPlatform.AMAZON: {
                "impressions": 38_200,
                "clicks": 734,
                "add_to_carts": 112,
                "orders": 48,
                "units_sold": 53,
                "ad_spend": 1180.0,
                "returns": 3,
                "inventory": 120,
            },
            ListingPlatform.TIKTOK_SHOP: {
                "impressions": 61_700,
                "clicks": 1487,
                "add_to_carts": 211,
                "orders": 59,
                "units_sold": 66,
                "ad_spend": 1680.0,
                "returns": 7,
                "inventory": 74,
            },
            ListingPlatform.SHOPIFY: {
                "impressions": 12_900,
                "clicks": 154,
                "add_to_carts": 31,
                "orders": 8,
                "units_sold": 9,
                "ad_spend": 330.0,
                "returns": 0,
                "inventory": 186,
            },
        }
        snapshots: list[PerformanceSnapshot] = []
        for platform in package.platforms:
            metrics = demo_metrics[platform]
            snapshots.append(
                self.create_snapshot(
                    PerformanceSnapshotRequest(
                        package_id=package_id,
                        platform=platform,
                        period_start=start,
                        period_end=end,
                        revenue=round(metrics["units_sold"] * price, 2),
                        source=PerformanceSource.MOCK_PLATFORM_API,
                        actor=actor,
                        **metrics,
                    )
                )
            )
        return snapshots

    def list_snapshots(
        self, package_id: UUID | None = None, limit: int = 100
    ) -> list[PerformanceSnapshot]:
        snapshots = [
            PerformanceSnapshot.model_validate(payload)
            for payload in self.state_store.list("performance_snapshot")
        ]
        if package_id:
            snapshots = [item for item in snapshots if item.package_id == package_id]
        return sorted(
            snapshots, key=lambda item: item.captured_at, reverse=True
        )[:limit]

    def latest_snapshots(self, package_id: UUID) -> list[PerformanceSnapshot]:
        package = self._get_published_package(package_id)
        snapshots = self.list_snapshots(package_id, limit=500)
        latest: dict[ListingPlatform, PerformanceSnapshot] = {}
        for snapshot in snapshots:
            latest.setdefault(snapshot.platform, snapshot)
        missing = [item.value for item in package.platforms if item not in latest]
        if missing:
            raise PerformanceConflictError(
                f"performance snapshots are missing for: {', '.join(missing)}"
            )
        return [latest[platform] for platform in package.platforms]

    def analyze(self, package_id: UUID, actor: str) -> PerformanceAnalysisReport:
        package = self._get_published_package(package_id)
        snapshots = self.latest_snapshots(package_id)
        skill = self.skill_registry.get("commerce-performance-optimization")
        report = skill.execute(package, snapshots, actor)
        self.state_store.put(
            "performance_report",
            str(report.report_id),
            report.model_dump(mode="json"),
        )
        return report

    def get_report(self, report_id: UUID) -> PerformanceAnalysisReport:
        payload = self.state_store.get("performance_report", str(report_id))
        if not payload:
            raise PerformanceNotFoundError("performance report not found")
        return PerformanceAnalysisReport.model_validate(payload)

    def list_reports(self, limit: int = 50) -> list[PerformanceAnalysisReport]:
        reports = [
            PerformanceAnalysisReport.model_validate(payload)
            for payload in self.state_store.list("performance_report")
        ]
        return sorted(reports, key=lambda item: item.created_at, reverse=True)[:limit]


@lru_cache
def get_commerce_performance_service() -> CommercePerformanceService:
    return CommercePerformanceService()
