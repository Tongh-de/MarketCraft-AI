from fastapi import APIRouter, HTTPException, status

from app.domain.models import ProductRecord, ProductSearchRequest, ProductSearchResponse
from app.services.product_catalog import get_product_catalog

router = APIRouter(prefix="/products", tags=["products"])


@router.put("/{sku}", response_model=ProductRecord)
def upsert_product(sku: str, product: ProductRecord) -> ProductRecord:
    if sku != product.sku:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="path sku must match payload sku",
        )
    return get_product_catalog().upsert(product)


@router.get("/{sku}", response_model=ProductRecord)
def get_product(sku: str) -> ProductRecord:
    product = get_product_catalog().get(sku)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return product


@router.post("/search/query", response_model=ProductSearchResponse)
def search_products(request: ProductSearchRequest) -> ProductSearchResponse:
    items = get_product_catalog().search(request)
    return ProductSearchResponse(total=len(items), items=items)
