from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import (
    Discrepancy,
    GoodsReceiptLine,
    GoodsReceipt,
    Invoice,
    LineItem,
    MatchResult,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.schemas.matching import DiscrepancyResponse, MatchResultResponse
from app.services.audit_service import AuditService


class MatchingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def match_invoice(self, invoice_id: str) -> MatchResultResponse:
        invoice = self.db.get(Invoice, invoice_id)
        if invoice is None:
            raise ValueError("Invoice not found")

        purchase_order = self._find_purchase_order(invoice)
        discrepancies = self._detect_discrepancies(invoice, purchase_order)
        status = "MATCHED" if not discrepancies else "DISCREPANCY"

        match_result = MatchResult(
            id=str(uuid4()),
            invoice_id=invoice.id,
            purchase_order_id=purchase_order.id if purchase_order else None,
            status=status,
        )
        self.db.add(match_result)
        self.db.flush()

        for code, severity, message in discrepancies:
            self.db.add(
                Discrepancy(
                    id=str(uuid4()),
                    match_result_id=match_result.id,
                    code=code,
                    severity=severity,
                    message=message,
                )
            )

        AuditService(self.db).record(
            tenant_id=invoice.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action=f"match:{status}",
            details="; ".join(message for _, _, message in discrepancies) or "Invoice matched",
        )
        self.db.commit()
        return MatchResultResponse(
            invoice_id=invoice.id,
            status=status,
            purchase_order_id=match_result.purchase_order_id,
            discrepancies=[
                DiscrepancyResponse(code=code, severity=severity, message=message)
                for code, severity, message in discrepancies
            ],
        )

    def _find_purchase_order(self, invoice: Invoice) -> PurchaseOrder | None:
        if not invoice.po_reference:
            return None
        return (
            self.db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.tenant_id == invoice.tenant_id,
                PurchaseOrder.po_number == invoice.po_reference,
            )
            .first()
        )

    def _detect_discrepancies(
        self,
        invoice: Invoice,
        purchase_order: PurchaseOrder | None,
    ) -> list[tuple[str, str, str]]:
        discrepancies: list[tuple[str, str, str]] = []
        if purchase_order is None:
            discrepancies.append(("MISSING_PO", "ERROR", "No purchase order matched the invoice PO reference"))
            return discrepancies

        invoice_total = self._money(invoice.amount)
        po_total = self._money(purchase_order.total_amount)
        if invoice_total is None:
            discrepancies.append(("MISSING_TOTAL", "ERROR", "Invoice total was not extracted"))
        if invoice_total is not None and po_total is not None:
            variance = abs(invoice_total - po_total)
            allowed = po_total * Decimal("0.02")
            if variance > allowed:
                discrepancies.append(
                    (
                        "PRICE_VARIANCE",
                        "ERROR",
                        f"Invoice total {invoice_total} differs from PO total {po_total} by more than 2%",
                    )
                )
        discrepancies.extend(self._detect_line_discrepancies(invoice, purchase_order))
        return discrepancies

    def _detect_line_discrepancies(
        self,
        invoice: Invoice,
        purchase_order: PurchaseOrder,
    ) -> list[tuple[str, str, str]]:
        invoice_lines = self.db.query(LineItem).filter(LineItem.invoice_id == invoice.id).all()
        po_lines = (
            self.db.query(PurchaseOrderLine)
            .filter(PurchaseOrderLine.purchase_order_id == purchase_order.id)
            .all()
        )
        receipt_lines = (
            self.db.query(GoodsReceiptLine)
            .join(GoodsReceipt, GoodsReceiptLine.goods_receipt_id == GoodsReceipt.id)
            .filter(GoodsReceipt.purchase_order_id == purchase_order.id)
            .all()
        )
        if not invoice_lines or not po_lines:
            return []

        discrepancies: list[tuple[str, str, str]] = []
        po_by_description = {self._key(line.description): line for line in po_lines}
        receipt_qty_by_description: dict[str, Decimal] = {}
        for receipt_line in receipt_lines:
            key = self._key(receipt_line.description)
            receipt_qty_by_description[key] = receipt_qty_by_description.get(key, Decimal("0")) + (
                self._money(receipt_line.quantity_received) or Decimal("0")
            )

        for invoice_line in invoice_lines:
            key = self._key(invoice_line.description or "")
            po_line = po_by_description.get(key)
            if po_line is None:
                discrepancies.append(
                    (
                        "MISSING_PO_LINE",
                        "ERROR",
                        f"Invoice line '{invoice_line.description}' does not exist on matched PO",
                    )
                )
                continue

            invoice_qty = self._money(invoice_line.quantity)
            po_qty = self._money(po_line.quantity)
            if invoice_qty is not None and po_qty is not None and invoice_qty > po_qty:
                discrepancies.append(
                    (
                        "QUANTITY_MISMATCH",
                        "ERROR",
                        f"Invoice quantity {invoice_qty} exceeds PO quantity {po_qty} for '{invoice_line.description}'",
                    )
                )

            invoice_unit_price = self._money(invoice_line.unit_price)
            po_unit_price = self._money(po_line.unit_price)
            if invoice_unit_price is not None and po_unit_price is not None:
                allowed = po_unit_price * Decimal("0.02")
                if abs(invoice_unit_price - po_unit_price) > allowed:
                    discrepancies.append(
                        (
                            "LINE_PRICE_VARIANCE",
                            "ERROR",
                            f"Invoice unit price {invoice_unit_price} differs from PO unit price {po_unit_price} for '{invoice_line.description}'",
                        )
                    )

            received_qty = receipt_qty_by_description.get(key)
            if received_qty is not None and invoice_qty is not None and invoice_qty > received_qty:
                discrepancies.append(
                    (
                        "RECEIPT_QUANTITY_MISMATCH",
                        "ERROR",
                        f"Invoice quantity {invoice_qty} exceeds received quantity {received_qty} for '{invoice_line.description}'",
                    )
                )
            elif receipt_lines and received_qty is None:
                discrepancies.append(
                    (
                        "MISSING_RECEIPT_LINE",
                        "ERROR",
                        f"No goods receipt line found for '{invoice_line.description}'",
                    )
                )
        return discrepancies

    @staticmethod
    def _money(value: str | None) -> Decimal | None:
        if value is None:
            return None
        normalized = value.replace(",", "").replace("$", "").strip()
        try:
            return Decimal(normalized)
        except InvalidOperation:
            return None

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.lower().strip().split())
