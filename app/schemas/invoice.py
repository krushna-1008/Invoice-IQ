from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvoiceCreateResponse(BaseModel):
    invoice_id: str
    status: str
    duplicate: bool = False


class InvoiceDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    vendor_id: str
    invoice_number: str
    file_path: str
    file_hash: str
    storage_location: str
    status: str
    amount: str | None = None
    subtotal: str | None = None
    tax_amount: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    vendor_name: str | None = None
    po_reference: str | None = None
    extraction_confidence: str | None = None
    extraction_error: str | None = None
    created_at: datetime


class QueueResponse(BaseModel):
    invoice_id: str
    status: str
