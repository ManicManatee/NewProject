from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List

import httpx
import msal
from azure.identity import ManagedIdentityCredential

from .config import CertificateAuth, ClientSecretAuth, ManagedIdentityAuth, TenantConfig
from .audit import JsonAuditLogger

logger = logging.getLogger(__name__)


class GraphAuthenticator:
    """Handles token acquisition for Microsoft Graph across tenants.

    Supports client secret, certificate-based auth, and managed identities. Tokens are
    cached in memory by MSAL for confidentiality flows; managed identity relies on the
    platform cache.
    """

    def __init__(self, tenant_config: TenantConfig, audit_logger: JsonAuditLogger):
        self.tenant_config = tenant_config
        self.audit = audit_logger

    def acquire_token(self, scopes: Iterable[str]) -> str:
        auth_config = self.tenant_config.auth

        if isinstance(auth_config, ClientSecretAuth):
            app = msal.ConfidentialClientApplication(
                client_id=auth_config.client_id,
                client_credential=auth_config.client_secret.resolve(),
                authority=f"{auth_config.authority_host}/{self.tenant_config.tenant_id}",
                token_cache=msal.TokenCache(),
            )
            result = app.acquire_token_silent(list(scopes), account=None)
            if not result:
                result = app.acquire_token_for_client(scopes=list(scopes))
            token = self._extract_token(result)
            self.audit.info(
                "acquired_app_token",
                tenant_id=self.tenant_config.tenant_id,
                auth_type="client_secret",
            )
            return token

        if isinstance(auth_config, CertificateAuth):
            cert_path = Path(auth_config.certificate_path)
            certificate = self._load_certificate(cert_path)
            app = msal.ConfidentialClientApplication(
                client_id=auth_config.client_id,
                client_credential=certificate,
                authority=f"{auth_config.authority_host}/{self.tenant_config.tenant_id}",
                token_cache=msal.TokenCache(),
            )
            result = app.acquire_token_silent(list(scopes), account=None)
            if not result:
                result = app.acquire_token_for_client(scopes=list(scopes))
            token = self._extract_token(result)
            self.audit.info(
                "acquired_app_token",
                tenant_id=self.tenant_config.tenant_id,
                auth_type="certificate",
            )
            return token

        if isinstance(auth_config, ManagedIdentityAuth):
            credential = ManagedIdentityCredential(client_id=auth_config.client_id)
            result = credential.get_token(*scopes)
            self.audit.info(
                "acquired_app_token",
                tenant_id=self.tenant_config.tenant_id,
                auth_type="managed_identity",
            )
            return result.token

        raise ValueError("Unsupported authentication configuration")

    @staticmethod
    def _extract_token(result: dict) -> str:
        if not result or "access_token" not in result:
            raise RuntimeError(f"Token acquisition failed: {json.dumps(result)}")
        return result["access_token"]

    def _load_certificate(self, path: Path) -> dict:
        password = None
        auth_config = self.tenant_config.auth
        if isinstance(auth_config, CertificateAuth) and auth_config.certificate_password:
            password = auth_config.certificate_password.resolve()
        try:
            with path.open("rb") as handle:
                certificate_bytes = handle.read()
        except OSError as exc:
            raise RuntimeError(f"Failed to read certificate at {path}: {exc}") from exc

        return {"private_key": certificate_bytes, "thumbprint": None, "passphrase": password}
