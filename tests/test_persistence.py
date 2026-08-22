from app.domain.models import ProductRecord, ProductSearchRequest
from app.services.persistence import SQLAlchemyJsonStateStore
from app.services.product_catalog import InMemoryProductCatalog


def test_sql_store_persists_product_across_repository_instances(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'state.db'}"
    first_store = SQLAlchemyJsonStateStore(database_url)
    first_catalog = InMemoryProductCatalog(state_store=first_store)
    first_catalog.upsert(
        ProductRecord(
            sku="PERSIST-001",
            name="持久化测试商品",
            category="咖啡杯",
            description="用于验证数据库持久化的商品记录。",
            target_audience="测试用户",
        )
    )

    second_catalog = InMemoryProductCatalog(
        state_store=SQLAlchemyJsonStateStore(database_url)
    )
    loaded = second_catalog.get("PERSIST-001")
    searched = second_catalog.search(ProductSearchRequest(query="持久化 商品"))
    assert loaded is not None
    assert loaded.sku == "PERSIST-001"
    assert searched[0].sku == "PERSIST-001"
