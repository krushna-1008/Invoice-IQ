from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.postgres import Base
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
from app.services.analytics_service import AnalyticsService
from app.services.approval_service import ApprovalService
from app.services.cache_service import CacheService, VendorIntelligenceService
from app.services.matching_service import MatchingService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def seed_invoice_with_po(db_session, amount: str = "110.00") -> Invoice:
    repository = InvoiceRepository(db_session)
    repository.ensure_tenant("tenant-1")
    repository.ensure_vendor("tenant-1", "vendor-1")
    db_session.add(
        PurchaseOrder(
            id="po-1",
            tenant_id="tenant-1",
            vendor_id="vendor-1",
            po_number="PO-1",
            total_amount="110.00",
            currency="USD",
            status="OPEN",
        )
    )
    invoice = Invoice(
        id=str(uuid4()),
        tenant_id="tenant-1",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
        file_path=str(Path("storage") / "invoice.pdf"),
        file_hash="hash",
        storage_location="local",
        status=InvoiceStatus.EXTRACTED,
        amount=amount,
        currency="USD",
        po_reference="PO-1",
    )
    return repository.create_invoice(invoice)


def seed_invoice_with_three_way_lines(db_session) -> Invoice:
    invoice = seed_invoice_with_po(db_session, amount="110.00")
    db_session.add(
        PurchaseOrderLine(
            id="po-line-1",
            purchase_order_id="po-1",
            description="Paper",
            quantity="10",
            unit_price="10.00",
            total_amount="100.00",
        )
    )
    receipt = GoodsReceipt(
        id="receipt-1",
        purchase_order_id="po-1",
        receipt_number="GR-1",
        status="RECEIVED",
    )
    db_session.add(receipt)
    db_session.add(
        GoodsReceiptLine(
            id="receipt-line-1",
            goods_receipt_id="receipt-1",
            description="Paper",
            quantity_received="10",
        )
    )
    db_session.add(
        LineItem(
            id="invoice-line-1",
            invoice_id=invoice.id,
            description="Paper",
            quantity="12",
            unit_price="11.00",
            total_amount="132.00",
        )
    )
    db_session.commit()
    return invoice


def test_matching_engine_matches_invoice_to_purchase_order(db_session):
    invoice = seed_invoice_with_po(db_session)

    result = MatchingService(db_session).match_invoice(invoice.id)

    assert result.status == "MATCHED"
    assert result.purchase_order_id == "po-1"
    assert result.discrepancies == []


def test_matching_engine_flags_price_variance(db_session):
    invoice = seed_invoice_with_po(db_session, amount="200.00")

    result = MatchingService(db_session).match_invoice(invoice.id)

    assert result.status == "DISCREPANCY"
    assert result.discrepancies[0].code == "PRICE_VARIANCE"


def test_matching_engine_flags_line_quantity_price_and_receipt_mismatches(db_session):
    invoice = seed_invoice_with_three_way_lines(db_session)

    result = MatchingService(db_session).match_invoice(invoice.id)
    codes = {discrepancy.code for discrepancy in result.discrepancies}

    assert result.status == "DISCREPANCY"
    assert {"QUANTITY_MISMATCH", "LINE_PRICE_VARIANCE", "RECEIPT_QUANTITY_MISMATCH"}.issubset(codes)


def test_approval_service_routes_by_amount(db_session):
    invoice = seed_invoice_with_po(db_session, amount="400.00")

    result = ApprovalService(db_session).route_invoice(invoice.id)

    assert result.route == "AUTO_APPROVED"
    assert result.approvals[0].status == "APPROVED"


def test_approval_tokens_are_signed_and_idempotent(db_session):
    invoice = seed_invoice_with_po(db_session, amount="900.00")

    routed = ApprovalService(db_session).route_invoice(invoice.id)
    token = routed.approvals[0].approval_token
    first = ApprovalService(db_session).decide_with_token(token, "APPROVED")
    second = ApprovalService(db_session).decide_with_token(token, "APPROVED")

    assert token is not None
    assert first.status == "APPROVED"
    assert second.status == "APPROVED"


def test_vendor_profile_and_analytics_summary(db_session):
    seed_invoice_with_po(db_session, amount="110.00")
    cache = CacheService()

    profile = VendorIntelligenceService(db_session, cache=cache).vendor_profile("tenant-1", "vendor-1")
    summary = AnalyticsService(db_session).weekly_spend_summary("tenant-1")

    assert profile["invoice_count"] == 1
    assert profile["total_spend"] == "110.00"
    assert summary["total_spend"] == "110.00"
    assert summary["spend_by_vendor"] == {"vendor-1": "110.00"}


def test_mcp_registry_imports():
    from app.mcp.server import mcp

    assert mcp is not None
