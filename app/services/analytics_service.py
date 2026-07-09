from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import Approval, Invoice


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def weekly_spend_summary(self, tenant_id: str) -> dict:
        invoices = self.db.query(Invoice).filter(Invoice.tenant_id == tenant_id).all()
        total_spend = sum((self._money(invoice.amount) or Decimal("0")) for invoice in invoices)
        by_vendor: dict[str, Decimal] = {}
        flagged = []
        for invoice in invoices:
            by_vendor.setdefault(invoice.vendor_id, Decimal("0"))
            by_vendor[invoice.vendor_id] += self._money(invoice.amount) or Decimal("0")
            if invoice.status in {"FAILED", "NEEDS_REVIEW"}:
                flagged.append(
                    {
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.invoice_number,
                        "status": invoice.status,
                    }
                )

        pending_approvals = (
            self.db.query(Approval)
            .filter(Approval.tenant_id == tenant_id, Approval.status == "PENDING")
            .count()
        )
        return {
            "tenant_id": tenant_id,
            "invoice_count": len(invoices),
            "total_spend": str(total_spend),
            "spend_by_vendor": {vendor_id: str(amount) for vendor_id, amount in by_vendor.items()},
            "pending_approvals": pending_approvals,
            "flagged_invoices": flagged,
        }

    @staticmethod
    def _money(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value.replace(",", "").replace("$", "").strip())
        except InvalidOperation:
            return None
