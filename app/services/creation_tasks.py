from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from app.domain.creation import (
    CreateCreationTaskRequest,
    CreationTask,
    CreationTaskStatus,
)
from app.plugins.base import CreativePluginError
from app.plugins.registry import CreativePluginRegistry, get_creative_plugin_registry
from app.services.persistence import JsonStateStore, get_state_store
from app.skills.base import SkillNotFoundError
from app.skills.registry import SkillRegistry, get_skill_registry


class CreationTaskNotFoundError(Exception):
    pass


class CreationTaskService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        skill_registry: SkillRegistry | None = None,
        plugin_registry: CreativePluginRegistry | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.skill_registry = skill_registry or get_skill_registry()
        self.plugin_registry = plugin_registry or get_creative_plugin_registry()

    def _save(self, task: CreationTask) -> None:
        task.updated_at = datetime.now(UTC)
        self.state_store.put(
            "creation_task", str(task.task_id), task.model_dump(mode="json")
        )

    def create(self, request: CreateCreationTaskRequest) -> CreationTask:
        task = CreationTask(
            skill_id=request.skill_id,
            product=request.product,
            instruction=request.instruction,
            requested_outputs=request.requested_outputs,
            requested_by=request.actor,
            trace=["task_created"],
        )
        self._save(task)
        task.status = CreationTaskStatus.RUNNING
        task.progress = 10
        task.trace.append(f"select_skill:{request.skill_id}")
        self._save(task)

        try:
            skill = self.skill_registry.get(request.skill_id)
            result = skill.execute(request, self.plugin_registry)
        except (SkillNotFoundError, CreativePluginError, RuntimeError, ValueError) as error:
            task.status = CreationTaskStatus.FAILED
            task.error = str(error)
            task.trace.append("task_failed")
            self._save(task)
            return task

        task.plugin_id = result.plugin_id
        task.assets = result.assets
        task.trace.extend(result.trace)
        task.trace.append("task_completed")
        task.progress = 100
        task.status = CreationTaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        self._save(task)
        return task

    def get(self, task_id: UUID) -> CreationTask:
        payload = self.state_store.get("creation_task", str(task_id))
        if not payload:
            raise CreationTaskNotFoundError("creation task not found")
        return CreationTask.model_validate(payload)

    def list_tasks(self, limit: int = 50) -> list[CreationTask]:
        tasks = [
            CreationTask.model_validate(payload)
            for payload in self.state_store.list("creation_task")
        ]
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)[:limit]


@lru_cache
def get_creation_task_service() -> CreationTaskService:
    return CreationTaskService()
