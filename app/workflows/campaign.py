from typing import NotRequired, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.domain.models import (
    CampaignPackage,
    CampaignRequest,
    PlatformCopy,
    QualityIssue,
    RetrievedContext,
    VisualAnalysis,
)
from app.services.brand_repository import BrandRepository, get_brand_repository
from app.services.generator import ContentGenerator, get_generator
from app.services.quality import QualityService
from app.services.vision import VisionAnalyzer, get_vision_analyzer
from app.telemetry import traced


class CampaignState(TypedDict):
    request: CampaignRequest
    visual_analysis: NotRequired[VisualAnalysis]
    selling_points: NotRequired[list[str]]
    brand_context: NotRequired[list[str]]
    brand_citations: NotRequired[list[RetrievedContext]]
    copies: NotRequired[list[PlatformCopy]]
    poster_prompt: NotRequired[str]
    quality_score: NotRequired[int]
    quality_issues: NotRequired[list[QualityIssue]]
    trace: NotRequired[list[str]]
    result: NotRequired[CampaignPackage]


def build_campaign_graph(
    generator: ContentGenerator | None = None,
    brand_repository: BrandRepository | None = None,
    quality_service: QualityService | None = None,
    vision_analyzer: VisionAnalyzer | None = None,
):
    generator = generator or get_generator()
    brand_repository = brand_repository or get_brand_repository()
    quality_service = quality_service or QualityService()
    vision_analyzer = vision_analyzer or get_vision_analyzer()

    @traced("campaign.analyze_product_visuals")
    def analyze_product_visuals(state: CampaignState) -> dict:
        return {
            "visual_analysis": vision_analyzer.analyze(state["request"]),
            "trace": ["analyze_product_visuals"],
        }

    @traced("campaign.extract_selling_points")
    def extract_selling_points(state: CampaignState) -> dict:
        return {
            "selling_points": generator.extract_selling_points(state["request"]),
            "trace": [*state.get("trace", []), "extract_selling_points"],
        }

    @traced("campaign.retrieve_brand_context")
    def retrieve_brand_context(state: CampaignState) -> dict:
        request = state["request"]
        query = (
            f"{request.product.name} {request.product.category} "
            f"{request.objective} {request.product.target_audience}"
        )
        citations = brand_repository.retrieve(
            request.brand_id, request.product.category, query
        )
        return {
            "brand_context": [
                f"[{item.source}#{item.doc_id}] {item.title}：{item.content}"
                for item in citations
            ],
            "brand_citations": citations,
            "trace": [*state.get("trace", []), "retrieve_brand_context"],
        }

    @traced("campaign.generate_content")
    def generate_content(state: CampaignState) -> dict:
        return {
            "copies": generator.generate_platform_copies(
                state["request"], state["selling_points"], state["brand_context"]
            ),
            "poster_prompt": generator.generate_poster_prompt(
                state["request"], state["selling_points"]
            ),
            "trace": [*state.get("trace", []), "generate_content"],
        }

    @traced("campaign.quality_review")
    def quality_review(state: CampaignState) -> dict:
        score, issues = quality_service.review(state["request"], state["copies"])
        return {
            "quality_score": score,
            "quality_issues": issues,
            "trace": [*state.get("trace", []), "quality_review"],
        }

    @traced("campaign.package_result")
    def package_result(state: CampaignState) -> dict:
        request = state["request"]
        score = state["quality_score"]
        trace = [*state.get("trace", []), "package_result"]
        result = CampaignPackage(
            product_sku=request.product.sku,
            selling_points=state["selling_points"],
            brand_context=state["brand_context"],
            brand_citations=state["brand_citations"],
            visual_analysis=state["visual_analysis"],
            copies=state["copies"],
            poster_prompt=state["poster_prompt"],
            quality_score=score,
            quality_issues=state["quality_issues"],
            status="approved" if score >= 80 else "needs_review",
            trace=trace,
        )
        return {"result": result, "trace": trace}

    builder = StateGraph(CampaignState)
    builder.add_node("analyze_product_visuals", analyze_product_visuals)
    builder.add_node("extract_selling_points", extract_selling_points)
    builder.add_node("retrieve_brand_context", retrieve_brand_context)
    builder.add_node("generate_content", generate_content)
    builder.add_node("quality_review", quality_review)
    builder.add_node("package_result", package_result)
    builder.add_edge(START, "analyze_product_visuals")
    builder.add_edge("analyze_product_visuals", "extract_selling_points")
    builder.add_edge("extract_selling_points", "retrieve_brand_context")
    builder.add_edge("retrieve_brand_context", "generate_content")
    builder.add_edge("generate_content", "quality_review")
    builder.add_edge("quality_review", "package_result")
    builder.add_edge("package_result", END)
    return builder.compile(checkpointer=InMemorySaver())


campaign_graph = build_campaign_graph()


@traced("api.campaign.generate")
def run_campaign(request: CampaignRequest, thread_id: str) -> CampaignPackage:
    output = campaign_graph.invoke(
        {"request": request},
        {"configurable": {"thread_id": thread_id}},
    )
    return output["result"]
