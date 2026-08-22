from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.models import AuditEvent


class SkillPluginStatus(StrEnum):
    DRAFT = "draft"
    ENABLED = "enabled"
    DISABLED = "disabled"


class SkillRiskLevel(StrEnum):
    READ_ONLY = "read_only"
    REVIEW_REQUIRED = "review_required"


class SkillPluginCreateRequest(BaseModel):
    plugin_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=500)
    instructions: str = Field(min_length=10, max_length=5000)
    triggers: list[str] = Field(min_length=1, max_length=20)
    capabilities: list[str] = Field(min_length=1, max_length=30)
    tool_bindings: list[str] = Field(default_factory=list, max_length=30)
    risk_level: SkillRiskLevel = SkillRiskLevel.READ_ONLY
    actor: str = Field(default="skill-designer", min_length=2, max_length=100)

    @field_validator("triggers", "capabilities", "tool_bindings")
    @classmethod
    def unique_non_empty_values(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("list values must be unique")
        return normalized


class SkillPluginUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=10, max_length=500)
    instructions: str | None = Field(default=None, min_length=10, max_length=5000)
    triggers: list[str] | None = Field(default=None, min_length=1, max_length=20)
    capabilities: list[str] | None = Field(default=None, min_length=1, max_length=30)
    tool_bindings: list[str] | None = Field(default=None, max_length=30)
    risk_level: SkillRiskLevel | None = None
    change_note: str = Field(min_length=2, max_length=300)
    actor: str = Field(default="skill-designer", min_length=2, max_length=100)

    @model_validator(mode="after")
    def require_change(self):
        changed = self.model_dump(exclude={"actor", "change_note"}, exclude_none=True)
        if not changed:
            raise ValueError("at least one skill field must be provided")
        return self


class SkillAutoEditRequest(BaseModel):
    change_request: str = Field(min_length=5, max_length=1000)
    actor: str = Field(default="skill-ai-editor", min_length=2, max_length=100)


class SkillPluginStatusRequest(BaseModel):
    status: Literal["enabled", "disabled"]
    actor: str = Field(default="skill-admin", min_length=2, max_length=100)


class SkillInvocationRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    actor: str = Field(default="workspace-user", min_length=2, max_length=100)


class SkillPluginManifest(BaseModel):
    plugin_id: str
    name: str
    description: str
    version: str
    status: SkillPluginStatus
    instructions: str
    triggers: list[str]
    capabilities: list[str]
    tool_bindings: list[str]
    risk_level: SkillRiskLevel
    built_in: bool = False
    editable: bool = True
    auto_edit_history: list[str] = Field(default_factory=list)
    audit_log: list[AuditEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillInvocationPlan(BaseModel):
    execution_id: UUID = Field(default_factory=uuid4)
    plugin_id: str
    version: str
    status: Literal["planned"] = "planned"
    prompt: str
    matched_triggers: list[str]
    capabilities: list[str]
    planned_tools: list[str]
    approval_required: bool
    trace: list[str]
    mock: bool = True


class ExternalServiceKind(StrEnum):
    CREATIVE_GENERATION = "creative_generation"
    ECOMMERCE_PLATFORM = "ecommerce_platform"
    BUSINESS_SYSTEM = "business_system"
    NOTIFICATION = "notification"
    CUSTOM = "custom"


class ExternalServiceMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class ExternalServiceStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PENDING_CONFIGURATION = "pending_configuration"


class ExternalServiceCreateRequest(BaseModel):
    service_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$")
    name: str = Field(min_length=2, max_length=100)
    kind: ExternalServiceKind
    description: str = Field(min_length=5, max_length=500)
    base_url: str | None = Field(default=None, max_length=2000)
    auth_type: Literal["none", "api_key", "oauth2"] = "none"
    secret_reference: str | None = Field(default=None, max_length=200)
    capabilities: list[str] = Field(min_length=1, max_length=30)
    mode: ExternalServiceMode = ExternalServiceMode.MOCK
    actor: str = Field(default="integration-admin", min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_live_configuration(self):
        if self.mode == ExternalServiceMode.LIVE and not self.base_url:
            raise ValueError("live external services require base_url")
        if self.auth_type != "none" and not self.secret_reference:
            raise ValueError("authenticated services require secret_reference")
        return self


class ExternalServiceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=5, max_length=500)
    base_url: str | None = Field(default=None, max_length=2000)
    auth_type: Literal["none", "api_key", "oauth2"] | None = None
    secret_reference: str | None = Field(default=None, max_length=200)
    capabilities: list[str] | None = Field(default=None, min_length=1, max_length=30)
    mode: ExternalServiceMode | None = None
    actor: str = Field(default="integration-admin", min_length=2, max_length=100)

    @model_validator(mode="after")
    def require_change(self):
        changed = self.model_dump(exclude={"actor"}, exclude_none=True)
        if not changed:
            raise ValueError("at least one external service field must be provided")
        return self


class ExternalServiceConnector(BaseModel):
    service_id: str
    name: str
    kind: ExternalServiceKind
    description: str
    base_url: str | None = None
    auth_type: Literal["none", "api_key", "oauth2"]
    secret_reference: str | None = None
    capabilities: list[str]
    mode: ExternalServiceMode
    status: ExternalServiceStatus
    built_in: bool = False
    editable: bool = True
    audit_log: list[AuditEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExternalServiceHealthResult(BaseModel):
    service_id: str
    status: ExternalServiceStatus
    mode: ExternalServiceMode
    checked: bool
    message: str
    capabilities: list[str]
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
