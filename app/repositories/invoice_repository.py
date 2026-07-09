from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Invoice, LineItem, Tenant, Vendor
from app.schemas.extraction import InvoiceExtraction
from app.services.audit_service import AuditService


class DuplicateInvoiceError(Exception):
    def __init__(self, invoice: Invoice | None = None) -> None:
        super().__init__("Invoice already exists")
        self.invoice = invoice


class InvoiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, invoice_id: str) -> Invoice | None:
        return self.db.get(Invoice, invoice_id)

    def get_by_business_key(
        self,
        tenant_id: str,
        vendor_id: str,
        invoice_number: str,
    ) -> Invoice | None:
        return (
            self.db.query(Invoice)
            .filter(
                Invoice.tenant_id == tenant_id,
                Invoice.vendor_id == vendor_id,
                Invoice.invoice_number == invoice_number,
            )
            .first()
        )

    def ensure_tenant(self, tenant_id: str) -> Tenant:
        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None:
            tenant = Tenant(id=tenant_id)
            self.db.add(tenant)
            self.db.flush()
        return tenant

    def ensure_vendor(self, tenant_id: str, vendor_id: str) -> Vendor:
        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.tenant_id == tenant_id, Vendor.id == vendor_id)
            .first()
        )
        if vendor is None:
            vendor = Vendor(id=vendor_id, tenant_id=tenant_id, external_id=vendor_id)
            self.db.add(vendor)
            self.db.flush()
        return vendor

    def create_invoice(self, invoice: Invoice) -> Invoice:
        try:
            self.db.add(invoice)
            self.db.flush()
            AuditService(self.db).record(
                tenant_id=invoice.tenant_id,
                entity_type="invoice",
                entity_id=invoice.id,
                action="invoice_created",
            )
            self.db.commit()
            self.db.refresh(invoice)
            return invoice
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.get_by_business_key(
                invoice.tenant_id,
                invoice.vendor_id,
                invoice.invoice_number,
            )
            raise DuplicateInvoiceError(existing) from exc

    def update_status(self, invoice: Invoice, status: str) -> Invoice:
        invoice.status = status
        AuditService(self.db).record(
            tenant_id=invoice.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action=f"status:{status}",
        )
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def persist_extraction(
        self,
        invoice: Invoice,
        extraction: InvoiceExtraction,
        status: str,
    ) -> Invoice:
        invoice.status = status
        invoice.vendor_name = extraction.vendor_name
        invoice.invoice_date = extraction.invoice_date
        invoice.due_date = extraction.due_date
        invoice.currency = extraction.currency
        invoice.subtotal = extraction.subtotal
        invoice.tax_amount = extraction.tax_amount
        invoice.amount = extraction.total_amount
        invoice.po_reference = extraction.po_reference
        invoice.extraction_confidence = str(extraction.overall_confidence)
        invoice.extraction_error = None
        AuditService(self.db).record(
            tenant_id=invoice.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action=f"extraction:{status}",
        )

        self.db.query(LineItem).filter(LineItem.invoice_id == invoice.id).delete()
        for line_item in extraction.line_items:
            self.db.add(
                LineItem(
                    id=str(uuid4()),
                    invoice_id=invoice.id,
                    description=line_item.description,
                    quantity=line_item.quantity,
                    unit_price=line_item.unit_price,
                    tax_amount=line_item.tax_amount,
                    total_amount=line_item.total_amount,
                    confidence=str(line_item.confidence),
                )
            )

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def mark_failed(self, invoice: Invoice, error: str) -> Invoice:
        invoice.status = "FAILED"
        invoice.extraction_error = error[:2000]
        AuditService(self.db).record(
            tenant_id=invoice.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action="extraction:FAILED",
            details=invoice.extraction_error,
        )
        self.db.commit()
        self.db.refresh(invoice)
        return invoice
