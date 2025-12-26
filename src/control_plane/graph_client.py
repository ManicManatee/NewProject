from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, Optional

import httpx

from .audit import JsonAuditLogger
from .auth import GraphAuthenticator
from .config import TenantConfig

logger = logging.getLogger(__name__)


class GraphClient:
    """Tenant-scoped Microsoft Graph client with retry and logging."""

    def __init__(
        self,
        tenant_config: TenantConfig,
        authenticator: GraphAuthenticator,
        audit_logger: JsonAuditLogger,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.tenant_config = tenant_config
        self.authenticator = authenticator
        self.audit = audit_logger
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = httpx.Client(timeout=self.timeout)

    def _auth_header(self, scopes: Iterable[str]) -> Dict[str, str]:
        token = self.authenticator.acquire_token(scopes)
        return {"Authorization": f"Bearer {token}"}

    def request(
        self,
        method: str,
        url: str,
        scopes: Optional[Iterable[str]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        scopes = scopes or self.tenant_config.default_scopes
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_header(scopes))
        backoff = 1.0

        for attempt in range(1, self.max_retries + 2):
            response = self.session.request(method, url, headers=headers, **kwargs)
            if response.status_code in (429, 503, 504):
                retry_after = self._get_retry_after_seconds(response) or backoff
                self.audit.warning(
                    "graph_throttled",
                    tenant_id=self.tenant_config.tenant_id,
                    status=response.status_code,
                    retry_after=retry_after,
                    attempt=attempt,
                )
                time.sleep(retry_after)
                backoff = min(backoff * 2, 30)
                continue

            if response.status_code >= 400:
                self.audit.error(
                    "graph_request_failed",
                    tenant_id=self.tenant_config.tenant_id,
                    status=response.status_code,
                    url=url,
                    body=response.text,
                )
                response.raise_for_status()

            self.audit.info(
                "graph_request_succeeded",
                tenant_id=self.tenant_config.tenant_id,
                status=response.status_code,
                url=url,
            )
            return response

        raise RuntimeError("Maximum retry attempts exceeded for Graph request")

    def _get_retry_after_seconds(self, response: httpx.Response) -> Optional[float]:
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            return float(retry_after)
        except ValueError:
            return None

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.tenant_config.graph_base_url}{path}"
        return self.request("GET", url, **kwargs)

    def post(self, path: str, json: Any, **kwargs: Any) -> httpx.Response:
        url = f"{self.tenant_config.graph_base_url}{path}"
        return self.request("POST", url, json=json, **kwargs)
