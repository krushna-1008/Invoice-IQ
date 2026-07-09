from uuid import uuid4

from app.db.postgres import Base, SessionLocal, engine
from app.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceStatus,
    LineItem,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.repositories.invoice_repository import InvoiceRepository


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        repository = InvoiceRepository(db)
        repository.ensure_tenant("demo-tenant")
        repository.ensure_vendor("demo-tenant", "demo-vendor")
        existing = repository.get_by_business_key("demo-tenant", "demo-vendor", "INV-DEMO-1")
        if existing is not None:
            print(f"Demo invoice already exists: {existing.id}")
            return

        po_id = str(uuid4())
        po = PurchaseOrder(
            id=po_id,
            tenant_id="demo-tenant",
            vendor_id="demo-vendor",
            po_number="PO-DEMO-1",
            status="OPEN",
            total_amount="110.00",
            currency="USD",
        )
        db.add(po)
        db.add(
            PurchaseOrderLine(
                id=str(uuid4()),
                purchase_order_id=po_id,
                description="Cloud AP automation subscription",
                quantity="1",
                unit_price="110.00",
                total_amount="110.00",
            )
        )
        receipt_id = str(uuid4())
        db.add(
            GoodsReceipt(
                id=receipt_id,
                purchase_order_id=po_id,
                receipt_number="GR-DEMO-1",
                status="RECEIVED",
            )
        )
        db.add(
            GoodsReceiptLine(
                id=str(uuid4()),
                goods_receipt_id=receipt_id,
                description="Cloud AP automation subscription",
                quantity_received="1",
            )
        )
        invoice_id = str(uuid4())
        invoice = Invoice(
            id=invoice_id,
            tenant_id="demo-tenant",
            vendor_id="demo-vendor",
            invoice_number="INV-DEMO-1",
            file_path="storage/invoices/demo-tenant/demo.pdf",
            file_hash="demo",
            storage_location="local",
            status=InvoiceStatus.EXTRACTED,
            amount="110.00",
            currency="USD",
            po_reference="PO-DEMO-1",
        )
        repository.create_invoice(invoice)
        db.add(
            LineItem(
                id=str(uuid4()),
                invoice_id=invoice_id,
                description="Cloud AP automation subscription",
                quantity="1",
                unit_price="110.00",
                total_amount="110.00",
            )
        )
        db.commit()
        print(f"Loaded demo invoice: {invoice_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
