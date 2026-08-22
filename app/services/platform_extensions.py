from datetime import UTC, datetime
from functools import lru_cache

from app.domain.models import AuditEvent
from app.domain.platform_extensions import (
    ExternalServiceConnector,
    ExternalServiceCreateRequest,
    ExternalServiceHealthResult,
    ExternalServiceKind,
    ExternalServiceMode,
    ExternalServiceStatus,
    ExternalServiceUpdateRequest,
    SkillAutoEditRequest,
    SkillInvocationPlan,
    SkillInvocationRequest,
    SkillPluginCreateRequest,
    SkillPluginManifest,
    SkillPluginStatus,
    SkillPluginStatusRequest,
    SkillPluginUpdateRequest,
    SkillRiskLevel,
)
from app.services.persistence import JsonStateStore, get_state_store
from app.skills.registry import SkillRegistry, get_skill_registry


class PlatformExtensionNotFoundError(Exception):
    pass


class PlatformExtensionConflictError(Exception):
    pass


BUILT_IN_TOOL_BINDINGS = {
    "product-asset-generation": ["creation.create_task"],
    "competitor-visual-analysis": ["creation.analyze_competitors"],
    "poster-design": ["poster.create_project", "poster.update_project"],
    "product-listing-package": ["listing.create_package", "listing.submit_review"],
    "commerce-performance-optimization": ["performance.load", "performance.analyze"],
}


class SkillPluginService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.skill_registry = skill_registry or get_skill_registry()

    def _built_ins(self) -> dict[str, SkillPluginManifest]:
        manifests: dict[str, SkillPluginManifest] = {}
        for descriptor in self.skill_registry.list_descriptors():
            manifests[descriptor.skill_id] = SkillPluginManifest(
                plugin_id=descriptor.skill_id,
                name=descriptor.name,
                description=descriptor.description,
                version=descriptor.version,
                status=SkillPluginStatus.ENABLED,
                instructions=descriptor.description,
                triggers=[descriptor.name, descriptor.skill_id],
                capabilities=[item.value for item in descriptor.required_capabilities]
                or [descriptor.skill_id],
                tool_bindings=BUILT_IN_TOOL_BINDINGS.get(descriptor.skill_id, []),
                risk_level=(
                    SkillRiskLevel.REVIEW_REQUIRED
                    if descriptor.skill_id == "product-listing-package"
                    else SkillRiskLevel.READ_ONLY
                ),
                built_in=True,
                editable=False,
            )
        return manifests

    @staticmethod
    def _next_patch(version: str) -> str:
        major, minor, patch = (int(item) for item in version.split("."))
        return f"{major}.{minor}.{patch + 1}"

    def list_plugins(self) -> list[SkillPluginManifest]:
        custom = [
            SkillPluginManifest.model_validate(payload)
            for payload in self.state_store.list("skill_plugin")
        ]
        return list(self._built_ins().values()) + sorted(
            custom, key=lambda item: item.updated_at, reverse=True
        )

    def get(self, plugin_id: str) -> SkillPluginManifest:
        built_in = self._built_ins().get(plugin_id)
        if built_in:
            return built_in
        payload = self.state_store.get("skill_plugin", plugin_id)
        if not payload:
            raise PlatformExtensionNotFoundError("skill plugin not found")
        return SkillPluginManifest.model_validate(payload)

    def _save(self, plugin: SkillPluginManifest) -> None:
        plugin.updated_at = datetime.now(UTC)
        self.state_store.put(
            "skill_plugin", plugin.plugin_id, plugin.model_dump(mode="json")
        )

    def create(self, request: SkillPluginCreateRequest) -> SkillPluginManifest:
        if request.plugin_id in self._built_ins() or self.state_store.get(
            "skill_plugin", request.plugin_id
        ):
            raise PlatformExtensionConflictError("skill plugin ID already exists")
        plugin = SkillPluginManifest(
            plugin_id=request.plugin_id,
            name=request.name,
            description=request.description,
            version="1.0.0",
            status=SkillPluginStatus.DRAFT,
            instructions=request.instructions,
            triggers=request.triggers,
            capabilities=request.capabilities,
            tool_bindings=request.tool_bindings,
            risk_level=request.risk_level,
            audit_log=[
                AuditEvent(actor=request.actor, action="skill_plugin_created")
            ],
        )
        self._save(plugin)
        return plugin

    def update(
        self, plugin_id: str, request: SkillPluginUpdateRequest
    ) -> SkillPluginManifest:
        plugin = self.get(plugin_id)
        if not plugin.editable:
            raise PlatformExtensionConflictError(
                "built-in skills cannot be edited; create a custom skill instead"
            )
        for field in request.model_fields_set - {"actor", "change_note"}:
            value = getattr(request, field)
            if value is not None:
                setattr(plugin, field, value)
        plugin.version = self._next_patch(plugin.version)
        plugin.status = SkillPluginStatus.DRAFT
        plugin.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action="skill_plugin_updated",
                details={"change_note": request.change_note, "version": plugin.version},
            )
        )
        self._save(plugin)
        return plugin

    def auto_edit(
        self, plugin_id: str, request: SkillAutoEditRequest
    ) -> SkillPluginManifest:
        plugin = self.get(plugin_id)
        if not plugin.editable:
            raise PlatformExtensionConflictError(
                "built-in skills cannot be auto-edited; create a custom skill instead"
            )
        revision = request.change_request.strip()
        plugin.instructions = (
            f"{plugin.instructions.rstrip()}\n\n自动修订要求：{revision}"
        )[:5000]
        if revision not in plugin.triggers and len(plugin.triggers) < 20:
            plugin.triggers.append(revision[:120])
        plugin.auto_edit_history.append(revision)
        plugin.version = self._next_patch(plugin.version)
        plugin.status = SkillPluginStatus.DRAFT
        plugin.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action="skill_plugin_auto_edited",
                details={"change_request": revision, "version": plugin.version},
            )
        )
        self._save(plugin)
        return plugin

    def set_status(
        self, plugin_id: str, request: SkillPluginStatusRequest
    ) -> SkillPluginManifest:
        plugin = self.get(plugin_id)
        if not plugin.editable:
            raise PlatformExtensionConflictError("built-in skill status is managed by code")
        plugin.status = SkillPluginStatus(request.status)
        plugin.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action=f"skill_plugin_{request.status}",
                details={"version": plugin.version},
            )
        )
        self._save(plugin)
        return plugin

    def invoke(
        self, plugin_id: str, request: SkillInvocationRequest
    ) -> SkillInvocationPlan:
        plugin = self.get(plugin_id)
        if plugin.status != SkillPluginStatus.ENABLED:
            raise PlatformExtensionConflictError("skill plugin must be enabled before invocation")
        prompt_lower = request.prompt.lower()
        matched = [item for item in plugin.triggers if item.lower() in prompt_lower]
        return SkillInvocationPlan(
            plugin_id=plugin.plugin_id,
            version=plugin.version,
            prompt=request.prompt,
            matched_triggers=matched,
            capabilities=plugin.capabilities,
            planned_tools=plugin.tool_bindings,
            approval_required=plugin.risk_level == SkillRiskLevel.REVIEW_REQUIRED,
            trace=[
                "load_enabled_skill_manifest",
                "match_skill_triggers",
                "resolve_capabilities",
                "build_tool_execution_plan",
                "stop_before_external_write",
            ],
            mock=True,
        )


BUILT_IN_SERVICES = [
    ("comfyui.mock", "ComfyUI", ExternalServiceKind.CREATIVE_GENERATION, ["multi_view_generation", "virtual_try_on", "poster_generation"]),
    ("jimeng.mock", "即梦 AI", ExternalServiceKind.CREATIVE_GENERATION, ["poster_generation", "video_generation"]),
    ("amazon.mock", "Amazon Seller", ExternalServiceKind.ECOMMERCE_PLATFORM, ["listing_publish", "orders", "performance_read"]),
    ("tiktok-shop.mock", "TikTok Shop", ExternalServiceKind.ECOMMERCE_PLATFORM, ["listing_publish", "orders", "performance_read"]),
    ("shopify.mock", "Shopify", ExternalServiceKind.ECOMMERCE_PLATFORM, ["listing_publish", "performance_read"]),
    ("erp.mock", "ERP 库存系统", ExternalServiceKind.BUSINESS_SYSTEM, ["inventory_read", "inventory_reserve", "replenishment"]),
    ("feishu.mock", "飞书审批", ExternalServiceKind.NOTIFICATION, ["approval_notification"]),
]


class ExternalServiceConnectorService:
    def __init__(self, state_store: JsonStateStore | None = None) -> None:
        self.state_store = state_store or get_state_store()

    @staticmethod
    def _built_ins() -> dict[str, ExternalServiceConnector]:
        return {
            service_id: ExternalServiceConnector(
                service_id=service_id,
                name=name,
                kind=kind,
                description=f"{name} 确定性 Mock 适配器",
                base_url=None,
                auth_type="none",
                capabilities=capabilities,
                mode=ExternalServiceMode.MOCK,
                status=ExternalServiceStatus.CONNECTED,
                built_in=True,
                editable=False,
            )
            for service_id, name, kind, capabilities in BUILT_IN_SERVICES
        }

    def list_connectors(self) -> list[ExternalServiceConnector]:
        custom = [
            ExternalServiceConnector.model_validate(payload)
            for payload in self.state_store.list("external_service")
        ]
        return list(self._built_ins().values()) + sorted(
            custom, key=lambda item: item.updated_at, reverse=True
        )

    def get(self, service_id: str) -> ExternalServiceConnector:
        built_in = self._built_ins().get(service_id)
        if built_in:
            return built_in
        payload = self.state_store.get("external_service", service_id)
        if not payload:
            raise PlatformExtensionNotFoundError("external service not found")
        return ExternalServiceConnector.model_validate(payload)

    def _save(self, connector: ExternalServiceConnector) -> None:
        connector.updated_at = datetime.now(UTC)
        self.state_store.put(
            "external_service", connector.service_id, connector.model_dump(mode="json")
        )

    def create(
        self, request: ExternalServiceCreateRequest
    ) -> ExternalServiceConnector:
        if request.service_id in self._built_ins() or self.state_store.get(
            "external_service", request.service_id
        ):
            raise PlatformExtensionConflictError("external service ID already exists")
        connector = ExternalServiceConnector(
            service_id=request.service_id,
            name=request.name,
            kind=request.kind,
            description=request.description,
            base_url=request.base_url,
            auth_type=request.auth_type,
            secret_reference=request.secret_reference,
            capabilities=request.capabilities,
            mode=request.mode,
            status=(
                ExternalServiceStatus.CONNECTED
                if request.mode == ExternalServiceMode.MOCK
                else ExternalServiceStatus.PENDING_CONFIGURATION
            ),
            audit_log=[
                AuditEvent(actor=request.actor, action="external_service_created")
            ],
        )
        self._save(connector)
        return connector

    def update(
        self, service_id: str, request: ExternalServiceUpdateRequest
    ) -> ExternalServiceConnector:
        connector = self.get(service_id)
        if not connector.editable:
            raise PlatformExtensionConflictError(
                "built-in service connectors cannot be edited"
            )
        for field in request.model_fields_set - {"actor"}:
            value = getattr(request, field)
            if value is not None:
                setattr(connector, field, value)
        connector.status = (
            ExternalServiceStatus.CONNECTED
            if connector.mode == ExternalServiceMode.MOCK
            else ExternalServiceStatus.PENDING_CONFIGURATION
        )
        connector.audit_log.append(
            AuditEvent(actor=request.actor, action="external_service_updated")
        )
        self._save(connector)
        return connector

    def check_health(self, service_id: str) -> ExternalServiceHealthResult:
        connector = self.get(service_id)
        if connector.mode == ExternalServiceMode.MOCK:
            return ExternalServiceHealthResult(
                service_id=service_id,
                status=ExternalServiceStatus.CONNECTED,
                mode=connector.mode,
                checked=True,
                message="Mock 适配器可用；未访问真实外部服务。",
                capabilities=connector.capabilities,
            )
        return ExternalServiceHealthResult(
            service_id=service_id,
            status=ExternalServiceStatus.PENDING_CONFIGURATION,
            mode=connector.mode,
            checked=False,
            message=(
                "已保存接口配置，但尚未执行真实网络联调；请在部署环境注入密钥并安装对应适配器。"
            ),
            capabilities=connector.capabilities,
        )


@lru_cache
def get_skill_plugin_service() -> SkillPluginService:
    return SkillPluginService()


@lru_cache
def get_external_service_connector_service() -> ExternalServiceConnectorService:
    return ExternalServiceConnectorService()
