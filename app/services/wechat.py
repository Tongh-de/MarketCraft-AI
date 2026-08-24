import json
import mimetypes
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.domain.models import AuditEvent
from app.domain.wechat import (
    WechatConfigurationStatus,
    WechatConnectionHealth,
    WechatDraftCreateRequest,
    WechatDraftRecord,
    WechatDraftStatus,
    WechatMaterialUploadResult,
    WechatMode,
    WechatPublicationStatus,
    WechatPublishRequest,
    WechatReviewRequest,
)
from app.services.persistence import JsonStateStore, get_state_store


class WechatNotFoundError(Exception):
    pass


class WechatConflictError(Exception):
    pass


class WechatConfigurationError(Exception):
    pass


class WechatApiError(Exception):
    def __init__(self, message: str, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class WechatHttpClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str = "application/json; charset=utf-8",
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        data = body
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}{query}",
            data=data,
            method=method,
            headers={"Content-Type": content_type},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise WechatApiError(f"WeChat HTTP {error.code}: {detail[:500]}") from error
        except (URLError, TimeoutError) as error:
            raise WechatApiError(f"WeChat network request failed: {error}") from error
        if result.get("errcode", 0) != 0:
            raise WechatApiError(
                (
                    f"WeChat API error {result.get('errcode')}: "
                    f"{result.get('errmsg', 'unknown error')}"
                ),
                result.get("errcode"),
            )
        return result


def _multipart_file(field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----MarketCraft{uuid4().hex}"
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


class WechatOfficialAccountService:
    def __init__(
        self,
        settings: Settings | None = None,
        state_store: JsonStateStore | None = None,
        http_client: WechatHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.state_store = state_store or get_state_store()
        self.mode = WechatMode(self.settings.wechat_mode)
        self.http = http_client or WechatHttpClient(
            self.settings.wechat_api_base, self.settings.wechat_timeout_seconds
        )
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)

    def configuration_status(self) -> WechatConfigurationStatus:
        configured = bool(self.settings.wechat_app_id and self.settings.wechat_app_secret)
        if self.mode == WechatMode.MOCK:
            message = (
                "Mock 模式可演示素材上传、草稿、审核和发布，"
                "不访问微信服务器。"
            )
        elif configured:
            message = (
                "Live 配置已加载；请确认公众号接口权限与服务器 IP 白名单。"
            )
        else:
            message = "Live 模式缺少 WECHAT_APP_ID 或 WECHAT_APP_SECRET。"
        return WechatConfigurationStatus(
            mode=self.mode,
            configured=self.mode == WechatMode.MOCK or configured,
            app_id_loaded=bool(self.settings.wechat_app_id),
            app_secret_loaded=bool(self.settings.wechat_app_secret),
            api_base=self.settings.wechat_api_base,
            message=message,
        )

    def _require_live_configuration(self) -> None:
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise WechatConfigurationError(
                "WECHAT_APP_ID and WECHAT_APP_SECRET are required in live mode"
            )

    def check_health(self) -> WechatConnectionHealth:
        if self.mode == WechatMode.MOCK:
            return WechatConnectionHealth(
                mode=self.mode,
                connected=True,
                message="Mock 公众号适配器可用；未访问微信服务器。",
            )
        self._token()
        return WechatConnectionHealth(
            mode=self.mode,
            connected=True,
            message="已成功获取微信 access_token，AppID、AppSecret 和 IP 白名单有效。",
        )

    def _token(self) -> str:
        self._require_live_configuration()
        now = datetime.now(UTC)
        if self._access_token and now < self._token_expires_at:
            return self._access_token
        result = self.http.request_json(
            "GET",
            "/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self.settings.wechat_app_id or "",
                "secret": self.settings.wechat_app_secret or "",
            },
        )
        token = result.get("access_token")
        if not token:
            raise WechatApiError("WeChat token response did not include access_token")
        self._access_token = token
        self._token_expires_at = now + timedelta(
            seconds=max(int(result.get("expires_in", 7200)) - 300, 60)
        )
        return token

    def upload_cover(
        self, filename: str, content: bytes
    ) -> WechatMaterialUploadResult:
        if not content:
            raise WechatConflictError("cover image is empty")
        if len(content) > self.settings.wechat_max_material_bytes:
            raise WechatConflictError("cover image exceeds configured upload limit")
        if self.mode == WechatMode.MOCK:
            return WechatMaterialUploadResult(
                media_id=f"mock-thumb-{uuid4().hex}",
                url=f"mock://wechat-material/{filename}",
                mode=self.mode,
                mock=True,
            )
        body, content_type = _multipart_file("media", filename, content)
        result = self.http.request_json(
            "POST",
            "/cgi-bin/material/add_material",
            params={"access_token": self._token(), "type": "image"},
            body=body,
            content_type=content_type,
        )
        return WechatMaterialUploadResult(
            media_id=result["media_id"],
            url=result.get("url"),
            mode=self.mode,
            mock=False,
        )

    def create_draft(self, request: WechatDraftCreateRequest) -> WechatDraftRecord:
        if self.mode == WechatMode.MOCK:
            external_media_id = f"mock-draft-{uuid4().hex}"
        else:
            result = self.http.request_json(
                "POST",
                "/cgi-bin/draft/add",
                params={"access_token": self._token()},
                payload={
                    "articles": [
                        article.model_dump(mode="json", exclude_none=True)
                        for article in request.articles
                    ]
                },
            )
            external_media_id = result["media_id"]
        record = WechatDraftRecord(
            external_media_id=external_media_id,
            articles=request.articles,
            mode=self.mode,
            created_by=request.actor,
            audit_log=[AuditEvent(actor=request.actor, action="wechat_draft_created")],
        )
        self._save(record)
        return record

    def list_drafts(self) -> list[WechatDraftRecord]:
        records = [
            WechatDraftRecord.model_validate(item)
            for item in self.state_store.list("wechat_draft")
        ]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def get_draft(self, draft_id: str) -> WechatDraftRecord:
        payload = self.state_store.get("wechat_draft", draft_id)
        if not payload:
            raise WechatNotFoundError("wechat draft not found")
        return WechatDraftRecord.model_validate(payload)

    def review(
        self, draft_id: str, request: WechatReviewRequest
    ) -> WechatDraftRecord:
        record = self.get_draft(draft_id)
        if record.status != WechatDraftStatus.DRAFT:
            raise WechatConflictError("only draft records can be reviewed")
        if request.reviewer == record.created_by:
            raise WechatConflictError("reviewer must be different from draft creator")
        record.reviewed_by = request.reviewer
        record.review_reason = request.reason
        record.status = (
            WechatDraftStatus.APPROVED
            if request.action == "approve"
            else WechatDraftStatus.REJECTED
        )
        record.audit_log.append(
            AuditEvent(
                actor=request.reviewer,
                action=f"wechat_draft_{request.action}d",
                details={"reason": request.reason or ""},
            )
        )
        self._save(record)
        return record

    def publish(
        self, draft_id: str, request: WechatPublishRequest
    ) -> WechatDraftRecord:
        record = self.get_draft(draft_id)
        if record.status != WechatDraftStatus.APPROVED:
            raise WechatConflictError("draft must be approved before publishing")
        try:
            if self.mode == WechatMode.MOCK:
                publish_id = f"mock-publish-{uuid4().hex}"
            else:
                result = self.http.request_json(
                    "POST",
                    "/cgi-bin/freepublish/submit",
                    params={"access_token": self._token()},
                    payload={"media_id": record.external_media_id},
                )
                publish_id = result["publish_id"]
            record.publish_id = publish_id
            record.status = WechatDraftStatus.SUBMITTED
            record.last_error = None
            record.audit_log.append(
                AuditEvent(actor=request.actor, action="wechat_publish_submitted")
            )
            self._save(record)
            return record
        except WechatApiError as error:
            record.last_error = str(error)
            record.audit_log.append(
                AuditEvent(actor=request.actor, action="wechat_publish_failed")
            )
            self._save(record)
            raise

    def publication_status(self, publish_id: str) -> WechatPublicationStatus:
        if self.mode == WechatMode.MOCK:
            return WechatPublicationStatus(
                publish_id=publish_id,
                publish_status=0,
                status="published",
                article_id=f"mock-article-{publish_id[-12:]}",
                mode=self.mode,
            )
        result = self.http.request_json(
            "POST",
            "/cgi-bin/freepublish/get",
            params={"access_token": self._token()},
            payload={"publish_id": publish_id},
        )
        status_code = result.get("publish_status")
        status_map = {
            0: "success",
            1: "publishing",
            2: "originality_failed",
            3: "common_failed",
            4: "platform_reviewing",
            5: "user_deleted",
        }
        return WechatPublicationStatus(
            publish_id=publish_id,
            publish_status=status_code,
            status=status_map.get(status_code, "unknown"),
            article_id=result.get("article_id"),
            article_detail=result.get("article_detail"),
            fail_idx=result.get("fail_idx", []),
            mode=self.mode,
        )

    def _save(self, record: WechatDraftRecord) -> None:
        record.updated_at = datetime.now(UTC)
        self.state_store.put(
            "wechat_draft", str(record.draft_id), record.model_dump(mode="json")
        )


@lru_cache
def get_wechat_service() -> WechatOfficialAccountService:
    return WechatOfficialAccountService()
