# Multi-Tenant Microsoft 365 Control Plane (Reference Implementation)

This repository contains a reference Python implementation of a control plane that securely manages multiple Microsoft 365 tenants. The design emphasizes tenant isolation, auditable operations, secure authentication, horizontal scalability, and an optional web UI for interactive operations and reporting.

## Goals

- Manage many tenants concurrently without cross-tenant data leakage.
- Support onboarding/offboarding flows with validation of required permissions.
- Execute read/write Microsoft Graph operations per tenant context using application and delegated permissions where appropriate.
- Provide strong logging, auditing, and error handling with retry logic for throttling.
- Serve as an enterprise/MSP-friendly blueprint that can be extended or containerized.

## Assumptions

- Authentication uses app registrations per tenant or a multi-tenant app consented in each tenant; no user secrets are stored.
- Secrets (client secrets, certificates, managed identity IDs) are delivered via secure stores such as Azure Key Vault and injected as environment variables or workload identity tokens.
- The control plane runs in an environment with outbound internet access to Microsoft Graph and (optionally) Azure Key Vault.

## Repository Layout

```
README.md                – Overview and usage guidance
requirements.txt         – Python dependencies
main.py                  – CLI entry point
webapp.py                – Flask-based GUI with reporting
src/control_plane/
  __init__.py            – Package marker
  config.py              – Tenant and auth configuration models
  auth.py                – Token acquisition helpers (certificate, secret, managed identity)
  graph_client.py        – Microsoft Graph wrapper with retries, throttling handling, and logging
  audit.py               – Audit/logging utilities with in-memory reporting store
  operations.py          – Example tenant-scoped Graph operations
  tenant_manager.py      – Tenant onboarding/offboarding and execution orchestration
config/tenants.example.yaml – Example configuration file
templates/               – HTML templates for the GUI
```

## Quick Start (CLI)

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create tenant configuration**

   Copy `config/tenants.example.yaml` to `config/tenants.yaml` and populate with your tenants. Secrets should reference secure stores (e.g., Azure Key Vault) or environment variables.

3. **Run the sample entry point**

   ```bash
   PYTHONPATH=src python main.py --config config/tenants.yaml --operation list-users --tenant-id <tenant-id>
   ```

   The example operations include listing users and creating security groups. Extend `operations.py` to add more use cases.

## Quick Start (GUI + Reporting)

1. Ensure dependencies and configuration are in place (as above).
2. Start the Flask app (uses `FLASK_SECRET_KEY` for session protection):

   ```bash
   FLASK_SECRET_KEY=please-change-me PYTHONPATH=src python webapp.py
   ```

3. Open `http://localhost:5000` to:
   - Select a tenant and run operations (list users, create security groups).
   - View recent audit events at `/audit` or download JSON from `/audit.json`.

Audit events are written to stdout and mirrored to an in-memory buffer for UI display. Wire the `JsonAuditLogger` to your logging sink or SIEM for production.

## Security Notes

- Avoid hard-coding tenant IDs, secrets, or certificate material in code or configuration. Use Key Vault references or environment variables.
- Use role-based access control (RBAC) to restrict who can run the control plane and who can onboard tenants.
- Prefer certificate-based authentication or managed identities over client secrets.
- Rotate credentials regularly and monitor audit logs for anomalous activity.

## Observability

All requests and results are logged with tenant-scoped correlation IDs. Audit events are available via the GUI and the `/audit.json` endpoint for downstream ingestion. The `audit.py` module provides a JSON logger that can be enriched per deployment.

## Extensibility

This reference is deliberately modular:
- Swap `GraphClient` transport or retry strategies.
- Implement custom onboarding checks in `TenantManager.validate_permissions`.
- Add workload-specific operations in `operations.py`.
- Replace the YAML config loader with a database-backed provider.

## Tests

Unit tests can be added under `tests/` to exercise configuration parsing and error handling. The current code focuses on demonstrating architecture and patterns rather than covering all test cases.
