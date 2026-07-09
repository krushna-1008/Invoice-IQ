"""create ingestion tables

Revision ID: 20260617_0001
Revises:
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260617_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vendors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id", "tenant_id"),
    )
    op.create_index(op.f("ix_vendors_tenant_id"), "vendors", ["tenant_id"], unique=False)
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("vendor_id", sa.String(), nullable=False),
        sa.Column("invoice_number", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("storage_location", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("amount", sa.String(), nullable=True),
        sa.Column("subtotal", sa.String(), nullable=True),
        sa.Column("tax_amount", sa.String(), nullable=True),
        sa.Column("invoice_date", sa.String(), nullable=True),
        sa.Column("due_date", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("vendor_name", sa.String(), nullable=True),
        sa.Column("po_reference", sa.String(), nullable=True),
        sa.Column("extraction_confidence", sa.String(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "vendor_id"], ["vendors.tenant_id", "vendors.id"], name="fk_invoice_vendor_tenant"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "vendor_id", "invoice_number", name="uq_invoice_idempotency"),
    )
    op.create_index(op.f("ix_invoices_tenant_id"), "invoices", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_invoices_vendor_id"), "invoices", ["vendor_id"], unique=False)
    op.create_table(
        "line_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.String(), nullable=True),
        sa.Column("unit_price", sa.String(), nullable=True),
        sa.Column("tax_amount", sa.String(), nullable=True),
        sa.Column("total_amount", sa.String(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_line_items_invoice_id"), "line_items", ["invoice_id"], unique=False)
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("vendor_id", sa.String(), nullable=True),
        sa.Column("po_number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_amount", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "vendor_id"], ["vendors.tenant_id", "vendors.id"], name="fk_purchase_order_vendor_tenant"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "po_number", name="uq_purchase_order_tenant_number"),
    )
    op.create_index(op.f("ix_purchase_orders_tenant_id"), "purchase_orders", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_purchase_orders_vendor_id"), "purchase_orders", ["vendor_id"], unique=False)
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("purchase_order_id", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.String(), nullable=True),
        sa.Column("unit_price", sa.String(), nullable=True),
        sa.Column("total_amount", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_purchase_order_lines_purchase_order_id"), "purchase_order_lines", ["purchase_order_id"], unique=False)
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("purchase_order_id", sa.String(), nullable=False),
        sa.Column("receipt_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goods_receipts_purchase_order_id"), "goods_receipts", ["purchase_order_id"], unique=False)
    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("goods_receipt_id", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity_received", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["goods_receipt_id"], ["goods_receipts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goods_receipt_lines_goods_receipt_id"), "goods_receipt_lines", ["goods_receipt_id"], unique=False)
    op.create_table(
        "match_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("purchase_order_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_match_results_invoice_id"), "match_results", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_match_results_purchase_order_id"), "match_results", ["purchase_order_id"], unique=False)
    op.create_table(
        "discrepancies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("match_result_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["match_result_id"], ["match_results.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_discrepancies_match_result_id"), "discrepancies", ["match_result_id"], unique=False)
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("approver_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_approvals_token_hash"),
    )
    op.create_index(op.f("ix_approvals_invoice_id"), "approvals", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_approvals_tenant_id"), "approvals", ["tenant_id"], unique=False)
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_tenant_id"), "audit_log", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_tenant_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_approvals_tenant_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_invoice_id"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_index(op.f("ix_discrepancies_match_result_id"), table_name="discrepancies")
    op.drop_table("discrepancies")
    op.drop_index(op.f("ix_match_results_purchase_order_id"), table_name="match_results")
    op.drop_index(op.f("ix_match_results_invoice_id"), table_name="match_results")
    op.drop_table("match_results")
    op.drop_index(op.f("ix_goods_receipts_purchase_order_id"), table_name="goods_receipts")
    op.drop_index(op.f("ix_goods_receipt_lines_goods_receipt_id"), table_name="goods_receipt_lines")
    op.drop_table("goods_receipt_lines")
    op.drop_table("goods_receipts")
    op.drop_index(op.f("ix_purchase_order_lines_purchase_order_id"), table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index(op.f("ix_purchase_orders_vendor_id"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_tenant_id"), table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index(op.f("ix_line_items_invoice_id"), table_name="line_items")
    op.drop_table("line_items")
    op.drop_index(op.f("ix_invoices_vendor_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_tenant_id"), table_name="invoices")
    op.drop_table("invoices")
    op.drop_index(op.f("ix_vendors_tenant_id"), table_name="vendors")
    op.drop_table("vendors")
    op.drop_table("tenants")
