from app.db.postgres import SessionLocal
from app.models import Invoice
from app.services.approval_service import ApprovalService
from app.services.cache_service import VendorIntelligenceService

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None


class LocalToolRegistry:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, fn):
        self.tools[fn.__name__] = fn
        return fn


mcp = FastMCP("InvoiceIQ") if FastMCP else LocalToolRegistry()


@mcp.tool
def search_invoices(tenant_id: str, vendor_id: str | None = None, status: str | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(Invoice).filter(Invoice.tenant_id == tenant_id)
        if vendor_id:
            query = query.filter(Invoice.vendor_id == vendor_id)
        if status:
            query = query.filter(Invoice.status == status)
        return [
            {
                "id": invoice.id,
                "vendor_id": invoice.vendor_id,
                "invoice_number": invoice.invoice_number,
                "amount": invoice.amount,
                "status": invoice.status,
            }
            for invoice in query.limit(50).all()
        ]
    finally:
        db.close()


@mcp.tool
def get_invoice_detail(invoice_id: str) -> dict | None:
    db = SessionLocal()
    try:
        invoice = db.get(Invoice, invoice_id)
        if invoice is None:
            return None
        return {
            "id": invoice.id,
            "tenant_id": invoice.tenant_id,
            "vendor_id": invoice.vendor_id,
            "invoice_number": invoice.invoice_number,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "status": invoice.status,
            "po_reference": invoice.po_reference,
        }
    finally:
        db.close()


@mcp.tool
def approve_invoice(approval_id: str) -> dict:
    db = SessionLocal()
    try:
        return ApprovalService(db).decide(approval_id, "APPROVED").model_dump()
    finally:
        db.close()


@mcp.tool
def query_vendor_spend(tenant_id: str, vendor_id: str) -> dict:
    db = SessionLocal()
    try:
        return VendorIntelligenceService(db).vendor_profile(tenant_id, vendor_id)
    finally:
        db.close()


@mcp.tool
def export_to_xero(invoice_id: str) -> dict:
    return {
        "invoice_id": invoice_id,
        "status": "not_configured",
        "detail": "Xero export adapter is planned after approval workflow hardening.",
    }
