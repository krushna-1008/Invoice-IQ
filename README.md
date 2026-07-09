# InvoiceIQ

InvoiceIQ is an AI-native accounts-payable processing service. The current implementation follows the 8-week plan in the project PDFs:

- Week 1: tenant-aware ingest API, idempotency, Alembic schema, repository/service split.
- Week 2: Claude vision extraction boundary, structured Pydantic output, line-item persistence.
- Week 3: line-level three-way matching with discrepancy records.
- Week 4: approval routing workflow with signed idempotent approval tokens.
- Week 5: Redis-first vendor intelligence cache with local fallback.
- Week 6: MCP tool surface for invoice search, approval, vendor spend, and export stubs.
- Week 7: analytics summary, health/metrics endpoints, and append-only audit log service.
- Week 8: tests, Docker, Compose, CI, and demo data loader.

## Run Locally

```bash
C:\Users\krushna mohod\python.exe -m pip install -r requirements.txt
C:\Users\krushna mohod\python.exe -m pytest -q
C:\Users\krushna mohod\python.exe -m uvicorn app.main:app --reload
```

## Docker

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

## Demo Flow

Default local API keys are configured for development:

- `tenant-1`: `dev-secret`
- `demo-tenant`: `demo-secret`

Seed a complete demo invoice/PO/goods-receipt flow:

```bash
C:\Users\krushna mohod\python.exe scripts/load_demo_data.py
```

Then call the API with `X-API-Key: demo-secret`:

```bash
curl -H "X-API-Key: demo-secret" http://localhost:8000/v1/tenants/demo-tenant/analytics/weekly-spend
curl -X POST -H "X-API-Key: demo-secret" http://localhost:8000/v1/invoices/{invoice_id}/match
curl -X POST -H "X-API-Key: demo-secret" http://localhost:8000/v1/invoices/{invoice_id}/route-approval
```

System endpoints:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

## Important Environment Variables

- `DATABASE_URL`: defaults to local PostgreSQL.
- `REDIS_URL`: defaults to `redis://localhost:6379/0`.
- `INVOICEIQ_API_KEYS`: comma-separated `tenant_id:api_key` pairs.
- `CELERY_QUEUE_ENABLED`: set to `true` when Redis/Celery should receive jobs.
- `ANTHROPIC_API_KEY`: required for live Claude extraction.
- `ANTHROPIC_MODEL`: defaults to `claude-opus-4-8`.
- `APPROVAL_TOKEN_SECRET`: secret used to sign approval links.

## Resume Talking Points

- Implemented tenant-scoped idempotent ingestion guarded by database uniqueness.
- Added Claude Vision extraction behind a deterministic service boundary.
- Built line-level three-way invoice/PO/goods-receipt matching.
- Added signed, expiring, idempotent approval links.
- Exposed operational metrics and MCP tools for AI-assisted AP workflows.
