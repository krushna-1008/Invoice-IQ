# InvoiceIQ

InvoiceIQ is a production-style, AI-native accounts-payable automation project built with FastAPI, PostgreSQL, Redis, Celery, Claude Vision, Alembic, Docker, and MCP tooling.

It demonstrates a realistic invoice workflow:

```text
PDF upload
  -> idempotent ingest
  -> AI extraction
  -> line-item persistence
  -> three-way PO / goods receipt matching
  -> approval routing
  -> audit log + analytics + MCP tools
```

## Why This Project Exists

Accounts-payable teams still spend time downloading invoice PDFs, checking them against purchase orders, routing approvals manually, and re-entering data into accounting systems. InvoiceIQ shows how that workflow can be automated with a reliable backend architecture:

- PostgreSQL as the source of truth
- Redis and Celery for asynchronous processing
- Claude Vision for document extraction
- Tenant-scoped idempotent APIs
- Three-way matching for accounting controls
- Signed approval links for human-in-the-loop workflows
- MCP tools for AI-assisted invoice operations

## Features

### Ingestion

- Tenant-aware invoice upload API
- Duplicate prevention using `(tenant_id, vendor_id, invoice_number)`
- File hashing and local storage metadata
- Upload support for portal, webhook, and email-forwarding style endpoints
- API-key tenant isolation

### AI Extraction

- PDF-to-image rendering boundary with `pdf2image`
- Claude Vision extractor behind a testable service interface
- Pydantic validation for structured invoice output
- Field confidence and low-confidence review routing
- Line-item persistence

### Matching

- Invoice-to-purchase-order matching
- Price variance checks
- Line-level PO matching
- Goods receipt quantity checks
- Discrepancy records for auditability

### Approval Workflow

- Auto-approval below threshold
- Single and dual approver routing
- Signed approval tokens
- Expiring approval links
- Idempotent approve/reject handling

### Analytics And Operations

- Vendor profile cache with Redis fallback to in-memory cache
- Weekly spend summary
- Append-only audit log service
- Prometheus-style `/metrics`
- `/health` endpoint
- Docker Compose stack for API, worker, Postgres, and Redis
- GitHub Actions test workflow

### MCP Tools

The MCP server exposes:

- `search_invoices`
- `get_invoice_detail`
- `approve_invoice`
- `query_vendor_spend`
- `export_to_xero` placeholder

## Tech Stack

| Area | Tools |
| --- | --- |
| API | FastAPI, Pydantic v2 |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Queue | Redis, Celery |
| AI | Anthropic Claude Vision |
| Testing | Pytest, SQLite service tests, FastAPI TestClient |
| Deployment | Docker, Docker Compose |
| AI Tooling | FastMCP |

## Project Structure

```text
app/
  api/              FastAPI routes
  core/             settings and security helpers
  db/               SQLAlchemy engine/session setup
  mcp/              MCP tool server
  repositories/     database access layer
  schemas/          Pydantic models
  services/         domain workflows
  workers/          Celery app and extraction task
alembic/            database migrations
demo/               demo walkthrough
scripts/            demo data loader
tests/              service and API tests
```

## Quick Start With Docker

```bash
docker compose up --build
```

In a second terminal:

```bash
docker compose exec api alembic upgrade head
```

Open the API docs:

```text
http://localhost:8000/docs
```

## Local Development

On this machine, the working Python interpreter is:

```powershell
& "C:\Users\krushna mohod\python.exe" -m pip install -r requirements.txt
& "C:\Users\krushna mohod\python.exe" -m pytest -q
& "C:\Users\krushna mohod\python.exe" -m uvicorn app.main:app --reload
```

For WSL or Linux:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m uvicorn app.main:app --reload
```

## Environment Variables

Copy the example file and fill in real secrets:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis broker/cache URL |
| `INVOICEIQ_API_KEYS` | Comma-separated `tenant_id:api_key` pairs |
| `CELERY_QUEUE_ENABLED` | Set to `true` to dispatch Celery jobs |
| `ANTHROPIC_API_KEY` | Required for live Claude extraction |
| `ANTHROPIC_MODEL` | Required for live Claude extraction |
| `APPROVAL_TOKEN_SECRET` | Secret used to sign approval links |
| `APPROVAL_TOKEN_TTL_HOURS` | Approval link expiry window |

Development defaults include:

```text
tenant-1:dev-secret
demo-tenant:demo-secret
```

Use the API key as:

```text
X-API-Key: demo-secret
```

## Demo Flow

Seed demo data:

```bash
python scripts/load_demo_data.py
```

With Docker:

```bash
docker compose exec api python scripts/load_demo_data.py
```

Then open:

```text
http://localhost:8000/docs
```

Suggested demo path:

1. `GET /v1/tenants/demo-tenant/analytics/weekly-spend`
2. `POST /v1/invoices/{invoice_id}/match`
3. `POST /v1/invoices/{invoice_id}/route-approval`
4. Copy the returned `approval_token`
5. `POST /v1/approval-links/{token}/APPROVED`
6. `GET /metrics`

More details are in [demo/e2e_flow.md](demo/e2e_flow.md).

## API Examples

Upload an invoice:

```bash
curl -X POST http://localhost:8000/v1/invoices \
  -H "X-API-Key: demo-secret" \
  -F "tenant_id=demo-tenant" \
  -F "vendor_id=demo-vendor" \
  -F "invoice_number=INV-1001" \
  -F "file=@sample_invoice.pdf;type=application/pdf"
```

Run matching:

```bash
curl -X POST \
  -H "X-API-Key: demo-secret" \
  http://localhost:8000/v1/invoices/{invoice_id}/match
```

Route approval:

```bash
curl -X POST \
  -H "X-API-Key: demo-secret" \
  http://localhost:8000/v1/invoices/{invoice_id}/route-approval
```

Approve using a signed token:

```bash
curl -X POST http://localhost:8000/v1/approval-links/{approval_token}/APPROVED
```

## Testing

```bash
python -m pytest -q
python -m compileall app tests scripts
```

Current local verification:

```text
16 passed
compileall passed
imports passed
```

## Resume Bullet

Built InvoiceIQ, a production-style AI accounts-payable automation platform using FastAPI, PostgreSQL, Redis, Celery, Claude Vision, Alembic, Docker, and MCP. Implemented tenant-scoped idempotent ingestion, structured invoice extraction, line-level three-way matching, signed approval workflows, audit logging, analytics, API-key isolation, metrics, and containerized deployment.

## Current Limitations

- Live Claude extraction requires a valid `ANTHROPIC_API_KEY` and current `ANTHROPIC_MODEL`.
- Xero export is intentionally a placeholder, ready for a sandbox integration.
- Tests use SQLite and fakes for speed; adding Testcontainers for real Postgres/Redis would be the next production-hardening step.
- Approval notifications are modeled through signed links, but no SMTP provider is wired yet.
