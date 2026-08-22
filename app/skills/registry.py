from functools import lru_cache

from app.domain.creation import SkillDescriptor
from app.skills.base import EcommerceSkill, SkillNotFoundError
from app.skills.competitor_analysis import CompetitorVisualAnalysisSkill
from app.skills.poster_design import PosterDesignSkill
from app.skills.product_assets import ProductAssetGenerationSkill


class SkillRegistry:
    def __init__(self, skills: list[EcommerceSkill] | None = None) -> None:
        installed = skills or [
            ProductAssetGenerationSkill(),
            CompetitorVisualAnalysisSkill(),
            PosterDesignSkill(),
        ]
        self._skills = {skill.descriptor.skill_id: skill for skill in installed}

    def list_descriptors(self) -> list[SkillDescriptor]:
        return [skill.descriptor for skill in self._skills.values()]

    def get(self, skill_id: str) -> EcommerceSkill:
        skill = self._skills.get(skill_id)
        if not skill:
            raise SkillNotFoundError(f"skill not found: {skill_id}")
        return skill


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
