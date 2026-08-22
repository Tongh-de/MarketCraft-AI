import argparse
from pathlib import Path

from app.evaluation import evaluate_retrieval, load_eval_cases
from app.services.brand_repository import get_brand_repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MarketCraft brand retrieval")
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/eval/retrieval.json")
    )
    parser.add_argument("--top-k", type=int, default=4)
    args = parser.parse_args()
    report = evaluate_retrieval(
        get_brand_repository(), load_eval_cases(args.dataset), args.top_k
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
