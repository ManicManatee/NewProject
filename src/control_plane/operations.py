from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .graph_client import GraphClient


@dataclass
class TenantExecutionContext:
    tenant_id: str
    graph: GraphClient


class TenantOperations:
    """Collection of sample Graph operations executed within a tenant context."""

    def __init__(self, context: TenantExecutionContext):
        self.context = context

    def list_users(self, top: int = 10) -> List[Dict[str, Any]]:
        response = self.context.graph.get(f"/v1.0/users?$top={top}")
        data = response.json()
        return data.get("value", [])

    def create_security_group(self, display_name: str, description: str) -> Dict[str, Any]:
        payload = {
            "description": description,
            "displayName": display_name,
            "securityEnabled": True,
            "mailEnabled": False,
            "groupTypes": [],
        }
        response = self.context.graph.post("/v1.0/groups", json=payload)
        return response.json()
