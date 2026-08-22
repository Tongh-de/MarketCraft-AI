from functools import lru_cache

from app.domain.models import ProductRecord, ProductSearchRequest
from app.services.brand_repository import tokenize


class InMemoryProductCatalog:
    def __init__(self) -> None:
        self._products: dict[str, ProductRecord] = {}

    def upsert(self, product: ProductRecord) -> ProductRecord:
        existing = self._products.get(product.sku)
        if existing:
            product = product.model_copy(update={"version": existing.version + 1})
        self._products[product.sku] = product
        return product

    def get(self, sku: str) -> ProductRecord | None:
        return self._products.get(sku)

    def search(self, request: ProductSearchRequest) -> list[ProductRecord]:
        query_tokens = set(tokenize(request.query))
        scored: list[tuple[int, ProductRecord]] = []
        for product in self._products.values():
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
