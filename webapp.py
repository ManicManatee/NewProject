from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, redirect, render_template, request, url_for, flash

from control_plane.audit import InMemoryAuditStore, JsonAuditLogger
from control_plane.config import ControlPlaneConfig
from control_plane.tenant_manager import TenantManager


def create_app(config_path: str | os.PathLike[str] = "config/tenants.yaml") -> Flask:
    config = ControlPlaneConfig.load(Path(config_path))
    audit_store = InMemoryAuditStore()
    audit_logger = JsonAuditLogger(store=audit_store)
    manager = TenantManager(config, audit_logger=audit_logger)

    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-this-secret")
    app.config["TENANT_MANAGER"] = manager
    app.config["AUDIT_STORE"] = audit_store

    @app.route("/")
    def index() -> str:
        tenants = manager.config.tenants
        return render_template("index.html", tenants=tenants)

    @app.post("/operate")
    def operate() -> str:
        tenant_id = request.form.get("tenant_id")
        operation = request.form.get("operation")
        correlation_id = str(uuid.uuid4())
        result: Dict[str, Any] | List[Dict[str, Any]] | None = None

        if not tenant_id or not operation:
            flash("Tenant and operation are required", "danger")
            return redirect(url_for("index"))

        try:
            if operation == "list-users":
                top_raw = request.form.get("top")
                top = int(top_raw) if top_raw else 10
                result = manager.run_operation(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    operation=lambda ops: ops.list_users(top=top),
                )
            elif operation == "create-security-group":
                display_name = request.form.get("group_name")
                description = request.form.get("group_description")
                if not display_name or not description:
                    flash("Group name and description are required", "danger")
                    return redirect(url_for("index"))
                result = manager.run_operation(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    operation=lambda ops: ops.create_security_group(display_name=display_name, description=description),
                )
            else:
                flash("Unsupported operation", "danger")
                return redirect(url_for("index"))
        except Exception as exc:  # noqa: BLE001
            flash(f"Operation failed: {exc}", "danger")
            result = None

        return render_template(
            "index.html",
            tenants=manager.config.tenants,
            result=result,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            operation=operation,
        )

    @app.get("/audit")
    def audit() -> str:
        limit_param = request.args.get("limit")
        try:
            limit = int(limit_param) if limit_param else 100
        except ValueError:
            limit = 100
        events = audit_store.list(limit=limit)
        return render_template("audit.html", events=events, limit=limit)

    @app.get("/audit.json")
    def audit_json():
        limit_param = request.args.get("limit")
        try:
            limit = int(limit_param) if limit_param else 100
        except ValueError:
            limit = 100
        events = audit_store.list(limit=limit)
        payload = [
            {
                "timestamp": event.timestamp,
                "level": event.level,
                "message": event.message,
                "tenant_id": event.tenant_id,
                "correlation_id": event.correlation_id,
                "extra": event.extra,
            }
            for event in events
        ]
        return jsonify({"events": payload, "count": len(payload)})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
