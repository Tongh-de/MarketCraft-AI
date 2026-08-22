from app.domain.creation import CreationTask, PosterProject, SkillDescriptor
from app.domain.listings import (
    ListingAsset,
    ListingPackageRequest,
    ListingPlatform,
    ListingSkillResult,
    PlatformListingDraft,
)


class ProductListingPackageSkill:
    descriptor = SkillDescriptor(
        skill_id="product-listing-package",
        name="商品智能上架 Skill",
        description="组合商品素材、海报、文案、价格和库存，生成多平台上架草稿。",
        version="1.0.0",
        required_capabilities=[],
    )

    def execute(
        self,
        request: ListingPackageRequest,
        creation_task: CreationTask,
        poster_project: PosterProject | None,
    ) -> tuple[ListingSkillResult, list[ListingAsset]]:
        assets = [
            ListingAsset(
                asset_type=asset.kind.value,
                label=asset.label,
                url=asset.url,
                source="creation_task",
                mock=asset.mock,
            )
            for asset in creation_task.assets
        ]
        if poster_project:
            assets.append(
                ListingAsset(
                    asset_type="editable_poster",
                    label="可编辑商品海报",
                    url=poster_project.preview_url,
                    source="poster_project",
                    mock=poster_project.mock,
                )
            )

        drafts = [
            self._build_platform_draft(request, platform, assets)
            for platform in request.platforms
        ]
        return (
            ListingSkillResult(
                drafts=drafts,
                trace=[
                    "validate_creation_assets",
                    "map_product_fields",
                    "generate_platform_copies",
                    "apply_platform_asset_rules",
                    "validate_price_and_inventory",
                    "create_listing_drafts",
                ],
            ),
            assets,
        )

    def _build_platform_draft(
        self,
        request: ListingPackageRequest,
        platform: ListingPlatform,
        assets: list[ListingAsset],
    ) -> PlatformListingDraft:
        product = request.product
        attributes = [f"{key}: {value}" for key, value in list(product.attributes.items())[:5]]
        verified_points = attributes or ["商品信息以实际详情页为准"]
        if platform == ListingPlatform.AMAZON:
            title = f"{product.name} | {product.category} | {verified_points[0]}"
            description = f"{product.description}\n" + "\n".join(
                f"• {point}" for point in verified_points
            )
            tags = [product.category, product.name, "official listing"]
            allowed_assets = [
                item.url
                for item in assets
                if item.asset_type not in {"editable_poster", "short_video"}
            ][:8]
        elif platform == ListingPlatform.TIKTOK_SHOP:
            title = f"{product.name}｜{verified_points[0]}"
            description = f"{product.description}。{'；'.join(verified_points[:3])}。"
            tags = [product.category, "新品", "好物推荐"]
            allowed_assets = [item.url for item in assets][:9]
        else:
            title = product.name
            description = f"{product.description}\n\n{' | '.join(verified_points)}"
            tags = [product.category, "brand-store", "new-arrival"]
            allowed_assets = [item.url for item in assets][:12]
        return PlatformListingDraft(
            platform=platform,
            title=title[:200],
            description=description,
            bullet_points=verified_points,
            tags=tags,
            category=product.category,
            price=product.price,
            currency=product.currency,
            inventory=product.inventory,
            asset_urls=allowed_assets,
        )
