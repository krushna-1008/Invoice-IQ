from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class InvoiceStatus:
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    vendors: Mapped[list["Vendor"]] = relationship(back_populates="tenant")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="tenant", overlaps="vendor,invoices")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="tenant",
        overlaps="purchase_orders,vendor",
    )
    approvals: Mapped[list["Approval"]] = relationship(back_populates="tenant")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="tenant")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="vendors")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="vendor", overlaps="invoices,tenant")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="vendor",
        overlaps="purchase_orders,tenant",
    )


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "vendor_id"],
            ["vendors.tenant_id", "vendors.id"],
            name="fk_invoice_vendor_tenant",
        ),
        UniqueConstraint("tenant_id", "vendor_id", "invoice_number", name="uq_invoice_idempotency"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    storage_location: Mapped[str] = mapped_column(String, nullable=False, default="local")
    status: Mapped[str] = mapped_column(String, nullable=False, default=InvoiceStatus.RECEIVED)
    amount: Mapped[str | None] = mapped_column(String, nullable=True)
    subtotal: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    po_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    extraction_confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="invoices", overlaps="invoices,vendor")
    vendor: Mapped[Vendor] = relationship(back_populates="invoices", overlaps="invoices,tenant")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="invoice")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="invoice")
    match_results: Mapped[list["MatchResult"]] = relationship(back_populates="invoice")


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    total_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    invoice: Mapped[Invoice] = relationship(back_populates="line_items")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "vendor_id"],
            ["vendors.tenant_id", "vendors.id"],
            name="fk_purchase_order_vendor_tenant",
        ),
        UniqueConstraint("tenant_id", "po_number", name="uq_purchase_order_tenant_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    vendor_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    po_number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN")
    total_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(
        back_populates="purchase_orders",
        overlaps="purchase_orders,vendor",
    )
    vendor: Mapped[Vendor | None] = relationship(
        back_populates="purchase_orders",
        overlaps="purchase_orders,tenant",
    )
    goods_receipts: Mapped[list["GoodsReceipt"]] = relationship(back_populates="purchase_order")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    purchase_order_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price: Mapped[str | None] = mapped_column(String, nullable=True)
    total_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    purchase_order_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=False,
        index=True,
    )
    receipt_number: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="RECEIVED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="goods_receipts")
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="goods_receipt")


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    goods_receipt_id: Mapped[str] = mapped_column(
        ForeignKey("goods_receipts.id"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_received: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    goods_receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    purchase_order_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    invoice: Mapped[Invoice] = relationship(back_populates="match_results")
    purchase_order: Mapped[PurchaseOrder | None] = relationship()
    discrepancies: Mapped[list["Discrepancy"]] = relationship(back_populates="match_result")


class Discrepancy(Base):
    __tablename__ = "discrepancies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    match_result_id: Mapped[str] = mapped_column(
        ForeignKey("match_results.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="ERROR")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    match_result: Mapped[MatchResult] = relationship(back_populates="discrepancies")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    approver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    token_hash: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="approvals")
    invoice: Mapped[Invoice] = relationship(back_populates="approvals")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="audit_logs")
