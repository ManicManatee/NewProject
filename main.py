from __future__ import annotations

import argparse
import json
from pathlib import Path

from control_plane.audit import JsonAuditLogger
from control_plane.config import ControlPlaneConfig
from control_plane.tenant_manager import TenantManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-tenant Microsoft 365 control plane")
    parser.add_argument("--config", required=True, help="Path to tenant configuration YAML")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID to target")
    parser.add_argument(
        "--operation",
        required=True,
        choices=["list-users", "create-security-group"],
        help="Operation to run",
    )
    parser.add_argument("--group-name", help="Display name for group creation")
    parser.add_argument("--group-description", help="Description for group creation")
    parser.add_argument("--top", type=int, default=10, help="Number of users to list")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ControlPlaneConfig.load(Path(args.config))
    audit_logger = JsonAuditLogger()
    manager = TenantManager(config, audit_logger=audit_logger)

    if args.operation == "list-users":
        result = manager.run_operation(
            tenant_id=args.tenant_id,
            operation=lambda ops: ops.list_users(top=args.top),
        )
    elif args.operation == "create-security-group":
        if not args.group_name or not args.group_description:
            raise SystemExit("--group-name and --group-description are required for group creation")
        result = manager.run_operation(
            tenant_id=args.tenant_id,
            operation=lambda ops: ops.create_security_group(
                display_name=args.group_name,
                description=args.group_description,
            ),
        )
    else:
        raise SystemExit(f"Unsupported operation: {args.operation}")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
