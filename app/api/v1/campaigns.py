from uuid import uuid4

from fastapi import APIRouter, Header

from app.domain.models import CampaignPackage, CampaignRequest
from app.workflows.campaign import run_campaign


router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/generate", response_model=CampaignPackage)
def generate_campaign(
    request: CampaignRequest,
    x_thread_id: str | None = Header(default=None),
) -> CampaignPackage:
    thread_id = x_thread_id or str(uuid4())
    return run_campaign(request, thread_id)

