from functools import lru_cache

from app.domain.models import ProductRecord, ProductSearchRequest
from app.services.brand_repository import tokenize
from app.services.persistence import JsonStateStore, get_state_store


class InMemoryProductCatalog:
    def __init__(self, state_store: JsonStateStore | None = None) -> None:
        self._products: dict[str, ProductRecord] = {}
        self.state_store = state_store or get_state_store()

    def upsert(self, product: ProductRecord) -> ProductRecord:
        existing = self._products.get(product.sku)
        if existing:
            product = product.model_copy(update={"version": existing.version + 1})
        self._products[product.sku] = product
        self.state_store.put("product", product.sku, product.model_dump(mode="json"))
        return product

    def get(self, sku: str) -> ProductRecord | None:
        product = self._products.get(sku)
        if not product:
            payload = self.state_store.get("product", sku)
            if payload:
                product = ProductRecord.model_validate(payload)
                self._products[sku] = product
        return product

    def search(self, request: ProductSearchRequest) -> list[ProductRecord]:
        query_tokens = set(tokenize(request.query))
        scored: list[tuple[int, ProductRecord]] = []
        products = {
            ProductRecord.model_validate(payload).sku: ProductRecord.model_validate(payload)
            for payload in self.state_store.list("product")
        }
        products.update(self._products)
        for product in products.values():
            if request.brand_id and product.brand_id != request.brand_id:
                continue
            if request.category and product.category != request.category:
                continue
            text = f"{product.name} {product.category} {product.description} {product.attributes}"
            score = len(query_tokens & set(tokenize(text))) if query_tokens else 1
            if score:
                scored.append((score, product))
        scored.sort(key=lambda item: (item[0], item[1].version), reverse=True)
        return [product for _, product in scored[: request.limit]]


@lru_cache
def get_product_catalog() -> InMemoryProductCatalog:
    return InMemoryProductCatalog()
