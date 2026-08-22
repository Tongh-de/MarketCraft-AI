from fastapi import APIRouter, status

from app.domain.models import (
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.brand_repository import get_brand_repository

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def upsert_documents(documents: list[KnowledgeDocument]) -> dict[str, int]:
    get_brand_repository().upsert(documents)
    return {"upserted": len(documents)}


@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    results = get_brand_repository().search(
        request.query, request.brand_id, request.category, request.limit
    )
    return KnowledgeSearchResponse(query=request.query, results=results)
