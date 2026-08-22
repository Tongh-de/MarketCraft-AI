import json
from pathlib import Path


class BrandRepository:
    """Phase-1 local repository; phase 3 replaces it with hybrid RAG retrieval."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path("data/brands")

    def retrieve(self, brand_id: str, category: str) -> list[str]:
        path = self.data_dir / f"{brand_id}.json"
        if not path.exists():
            return [
                "不得使用无法验证的绝对化表述",
                "文案需要明确目标用户和具体使用场景",
                "卖点必须能追溯到商品输入信息",
            ]

        data = json.loads(path.read_text(encoding="utf-8"))
        context = [f"品牌语气：{data['tone']}"]
        context.extend(f"品牌规则：{item}" for item in data.get("rules", []))
        category_rule = data.get("category_rules", {}).get(category)
        if category_rule:
            context.append(f"品类规则：{category_rule}")
        return context

