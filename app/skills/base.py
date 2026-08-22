from abc import ABC, abstractmethod

from app.domain.creation import (
    CreateCreationTaskRequest,
    SkillDescriptor,
    SkillExecutionResult,
)
from app.plugins.registry import CreativePluginRegistry


class SkillNotFoundError(Exception):
    pass


class EcommerceSkill(ABC):
    descriptor: SkillDescriptor

    @abstractmethod
    def execute(
        self,
        request: CreateCreationTaskRequest,
        plugin_registry: CreativePluginRegistry,
    ) -> SkillExecutionResult: ...
