from pathlib import Path

from app.evaluation import evaluate_retrieval, load_eval_cases
from app.services.brand_repository import BrandRepository


def test_retrieval_evaluation_report_has_expected_metrics() -> None:
    cases = load_eval_cases(Path("data/eval/retrieval.json"))
    report = evaluate_retrieval(BrandRepository(), cases, top_k=4)
    assert report.cases == 4
    assert report.recall_at_k == 1.0
    assert report.citation_coverage == 1.0
    assert 0 < report.mrr <= 1
