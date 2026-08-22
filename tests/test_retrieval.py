from app.domain.models import KnowledgeDocument
from app.services.brand_repository import InMemoryHybridRetriever


def test_hybrid_retrieval_filters_brand_and_returns_citations() -> None:
    retriever = InMemoryHybridRetriever(
        documents=[
            KnowledgeDocument(
                doc_id="rule-1",
                brand_id="brand-a",
                title="保温杯规范",
                content="保温杯需要突出容量、材质和清洁方式。",
                category="咖啡杯",
                source="guide-a",
            ),
            KnowledgeDocument(
                doc_id="rule-2",
                brand_id="brand-b",
                title="其他品牌规范",
                content="其他品牌也可能描述容量。",
                category="咖啡杯",
                source="guide-b",
            ),
        ]
    )
    results = retriever.search("咖啡杯容量和材质", "brand-a", "咖啡杯")
    assert results[0].doc_id == "rule-1"
    assert results[0].source == "guide-a"
    assert all(result.doc_id != "rule-2" for result in results)


def test_upsert_replaces_same_document_id() -> None:
    retriever = InMemoryHybridRetriever()
    original = KnowledgeDocument(
        doc_id="rule-1",
        brand_id="brand-a",
        title="旧规则",
        content="旧规则内容不能继续使用。",
    )
    updated = original.model_copy(update={"title": "新规则", "content": "新的价格规则。"})
    retriever.upsert([original])
    retriever.upsert([updated])
    results = retriever.search("新的价格规则", "brand-a")
    assert results[0].title == "新规则"
