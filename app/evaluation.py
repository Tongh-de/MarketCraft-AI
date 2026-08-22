import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.brand_repository import BrandRepository


class RetrievalEvalCase(BaseModel):
    case_id: str
    query: str
    brand_id: str
    category: str | None = None
    expected_doc_ids: list[str] = Field(min_length=1)


class RetrievalEvalReport(BaseModel):
    cases: int
    recall_at_k: float
    mrr: float
    citation_coverage: float
    top_k: int


def load_eval_cases(path: Path) -> list[RetrievalEvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [RetrievalEvalCase.model_validate(item) for item in payload]


def evaluate_retrieval(
    repository: BrandRepository,
    cases: list[RetrievalEvalCase],
    top_k: int = 4,
) -> RetrievalEvalReport:
    if not cases:
        raise ValueError("evaluation dataset cannot be empty")
    hits = 0
    reciprocal_rank_sum = 0.0
    cited_results = 0
    total_results = 0
    for case in cases:
        results = repository.search(
            case.query, case.brand_id, case.category, limit=top_k
        )
        result_ids = [result.doc_id for result in results]
        expected = set(case.expected_doc_ids)
        if expected.intersection(result_ids):
            hits += 1
        for rank, doc_id in enumerate(result_ids, start=1):
            if doc_id in expected:
                reciprocal_rank_sum += 1 / rank
                break
        cited_results += sum(bool(result.source and result.doc_id) for result in results)
        total_results += len(results)
    return RetrievalEvalReport(
        cases=len(cases),
        recall_at_k=hits / len(cases),
        mrr=reciprocal_rank_sum / len(cases),
        citation_coverage=cited_results / total_results if total_results else 0.0,
        top_k=top_k,
    )
