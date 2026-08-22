from app.domain.models import ProductRecord, ProductSearchRequest
from app.services.product_catalog import InMemoryProductCatalog


def make_product() -> ProductRecord:
    return ProductRecord(
        sku="CUP-001",
        name="轻盈随行保温杯",
        category="咖啡杯",
        description="适合办公室和通勤使用的不锈钢保温杯。",
        attributes={"容量": "450ml"},
        target_audience="通勤用户",
    )


def test_product_upsert_increments_version_and_is_searchable() -> None:
    catalog = InMemoryProductCatalog()
    first = catalog.upsert(make_product())
    second = catalog.upsert(make_product().model_copy(update={"price": 129}))
    results = catalog.search(ProductSearchRequest(query="通勤 保温杯"))
    assert first.version == 1
    assert second.version == 2
    assert results[0].sku == "CUP-001"
