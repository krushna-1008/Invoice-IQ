from fastapi import FastAPI

from app.api.invoices import router as invoice_router
from app.api.system import router as system_router

app = FastAPI(
    title="InvoiceIQ Ingestion Service",
    version="0.1.0",
)

app.include_router(invoice_router, prefix="/v1")
app.include_router(system_router)
