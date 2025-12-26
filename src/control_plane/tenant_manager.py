from __future__ import annotations

import logging
import uuid
from typing import Callable, Dict, Iterable, Optional

from .audit import JsonAuditLogger
from .auth import GraphAuthenticator
from .config import ControlPlaneConfig, TenantConfig
from .graph_client import GraphClient
from .operations import TenantExecutionContext, TenantOperations

logger = logging.getLogger(__name__)


class TenantManager:
    """Central orchestrator for tenant onboarding, validation, and operations."""

    def __init__(self, config: ControlPlaneConfig, audit_logger: Optional[JsonAuditLogger] = None):
        self.config = config
        self.audit = audit_logger or JsonAuditLogger()
        self._tenant_cache: Dict[str, TenantConfig] = {tenant.tenant_id: tenant for tenant in config.tenants}

    def get_tenant(self, tenant_id: str) -> TenantConfig:
        tenant = self._tenant_cache.get(tenant_id)
        if not tenant:
            raise KeyError(f"Tenant {tenant_id} is not configured")
        return tenant

    def onboard_tenant(self, tenant: TenantConfig) -> None:
        self._tenant_cache[tenant.tenant_id] = tenant
        self.audit.info("tenant_onboarded", tenant_id=tenant.tenant_id, display_name=tenant.display_name)

    def offboard_tenant(self, tenant_id: str) -> None:
        self._tenant_cache.pop(tenant_id, None)
        self.audit.info("tenant_offboarded", tenant_id=tenant_id)

    def validate_permissions(self, tenant: TenantConfig) -> None:
        # Placeholder for custom validation logic (e.g., calling /oauth2PermissionGrants).
        self.audit.info(
            "tenant_validated",
            tenant_id=tenant.tenant_id,
            required_app_roles=tenant.required_application_roles,
            required_delegated_permissions=tenant.required_delegated_permissions,
        )

    def with_context(self, tenant_id: str) -> TenantExecutionContext:
        tenant = self.get_tenant(tenant_id)
        self.validate_permissions(tenant)
        authenticator = GraphAuthenticator(tenant, self.audit)
        graph_client = GraphClient(tenant_config=tenant, authenticator=authenticator, audit_logger=self.audit)
        return TenantExecutionContext(tenant_id=tenant.tenant_id, graph=graph_client)

    def run_operation(
        self,
        tenant_id: str,
        operation: Callable[[TenantOperations], object],
        correlation_id: Optional[str] = None,
    ) -> object:
        correlation_id = correlation_id or str(uuid.uuid4())
        context = self.with_context(tenant_id)
        self.audit.info("operation_started", tenant_id=tenant_id, correlation_id=correlation_id)
        ops = TenantOperations(context)
        result = operation(ops)
        self.audit.info("operation_completed", tenant_id=tenant_id, correlation_id=correlation_id)
        return result
