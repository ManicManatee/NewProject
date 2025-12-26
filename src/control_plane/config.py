from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SecretRef(BaseModel):
    """Reference to a secret source without storing the secret in code.

    Secrets should be supplied by secure stores (e.g., Azure Key Vault) or environment
    variables injected at runtime. The `resolve` method intentionally only supports
    environment variables by default to avoid accidental plaintext storage. Extend this
    class to integrate directly with your secrets provider.
    """

    env: Optional[str] = Field(
        default=None, description="Environment variable name containing the secret"
    )
    value: Optional[str] = Field(
        default=None,
        description="Inline value (use only for local development; avoid in production)",
    )
    key_vault_secret_uri: Optional[str] = Field(
        default=None,
        description="URI of the Key Vault secret. Resolve via managed identity at runtime.",
    )

    model_config = ConfigDict(extra="forbid")

    def resolve(self) -> str:
        if self.env:
            env_value = os.getenv(self.env)
            if env_value:
                return env_value
            raise ValueError(f"Environment variable {self.env} is not set")
        if self.value:
            return self.value
        if self.key_vault_secret_uri:
            raise ValueError(
                "Key Vault secret resolution is not implemented in SecretRef.resolve(). "
                "Fetch the secret via managed identity before invoking authentication."
            )
        raise ValueError("No secret reference provided for resolution")


class ClientSecretAuth(BaseModel):
    type: Literal["client_secret"]
    client_id: str
    client_secret: SecretRef
    authority_host: str = Field(
        default="https://login.microsoftonline.com",
        description="AAD authority host",
    )

    model_config = ConfigDict(extra="forbid")


class CertificateAuth(BaseModel):
    type: Literal["certificate"]
    client_id: str
    certificate_path: Path
    certificate_password: Optional[SecretRef] = None
    authority_host: str = Field(
        default="https://login.microsoftonline.com",
        description="AAD authority host",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("certificate_path")
    @classmethod
    def validate_cert_path(cls, value: Path) -> Path:
        if not value:
            raise ValueError("certificate_path is required for certificate auth")
        return value


class ManagedIdentityAuth(BaseModel):
    type: Literal["managed_identity"]
    client_id: Optional[str] = Field(
        default=None, description="Optional user-assigned managed identity client ID"
    )

    model_config = ConfigDict(extra="forbid")


AuthConfig = Union[ClientSecretAuth, CertificateAuth, ManagedIdentityAuth]


class TenantConfig(BaseModel):
    tenant_id: str
    display_name: Optional[str] = None
    auth: AuthConfig
    default_scopes: List[str] = Field(
        default_factory=lambda: ["https://graph.microsoft.com/.default"]
    )
    graph_base_url: str = Field(
        default="https://graph.microsoft.com",
        description="Graph endpoint. Override for national clouds if needed.",
    )
    required_application_roles: List[str] = Field(
        default_factory=list,
        description="App roles the service must hold in this tenant (validation only)",
    )
    required_delegated_permissions: List[str] = Field(
        default_factory=list,
        description="Delegated permissions expected when using OBO/delegated flows",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("default_scopes")
    @classmethod
    def ensure_scopes(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("At least one scope must be provided per tenant")
        return value


class ControlPlaneConfig(BaseModel):
    tenants: List[TenantConfig]

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ControlPlaneConfig":
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        return cls(**raw)
