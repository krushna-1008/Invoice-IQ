# InvoiceIQ End-to-End Demo

1. Start the stack:

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

2. Load demo data:

```bash
docker compose exec api python scripts/load_demo_data.py
```

3. Open Swagger:

```text
http://localhost:8000/docs
```

4. Use this header in protected endpoints:

```text
X-API-Key: demo-secret
```

5. Demo the workflow:

- `GET /v1/tenants/demo-tenant/analytics/weekly-spend`
- `POST /v1/invoices/{invoice_id}/match`
- `POST /v1/invoices/{invoice_id}/route-approval`
- Copy the returned approval token.
- `POST /v1/approval-links/{token}/APPROVED`
- `GET /metrics`

