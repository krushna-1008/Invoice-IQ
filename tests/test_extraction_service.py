from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.postgres import Base
from app.models import Invoice, InvoiceStatus, LineItem
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.extraction import ExtractedLineItem, InvoiceExtraction
from app.services.extraction_service import ExtractionError, ExtractionService


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


def create_invoice(db_session, tmp_path: Path) -> Invoice:
    repository = InvoiceRepository(db_session)
    repository.ensure_tenant("tenant-1")
    repository.ensure_vendor("tenant-1", "vendor-1")
    file_path = tmp_path / "invoice.pdf"
    file_path.write_bytes(b"%PDF-1.7 sample")
    invoice = Invoice(
        id="invoice-1",
        tenant_id="tenant-1",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
        file_path=str(file_path),
        file_hash="hash",
        storage_location="local",
        status=InvoiceStatus.QUEUED,
    )
    return repository.create_invoice(invoice)


class FakeExtractor:
    def __init__(self, confidence: float = 0.95) -> None:
        self.confidence = confidence

    def extract(self, file_path: Path) -> InvoiceExtraction:
        return InvoiceExtraction(
            vendor_name="Acme Supplies",
            invoice_number="INV-1001",
            invoice_date="2026-06-17",
            due_date="2026-07-17",
            currency="USD",
            subtotal="100.00",
            tax_amount="10.00",
            total_amount="110.00",
            po_reference="PO-42",
            line_items=[
                ExtractedLineItem(
                    description="Paper",
                    quantity="10",
                    unit_price="10.00",
                    tax_amount="10.00",
                    total_amount="110.00",
                    confidence=0.91,
                )
            ],
            field_confidence={"total_amount": 0.99, "invoice_number": 0.97},
            overall_confidence=self.confidence,
        )


class FailingExtractor:
    def extract(self, file_path: Path) -> InvoiceExtraction:
        raise ExtractionError("OCR failed")


def test_extract_invoice_persists_structured_fields_and_line_items(db_session, tmp_path):
    invoice = create_invoice(db_session, tmp_path)

    result = ExtractionService(
        InvoiceRepository(db_session),
        extractor=FakeExtractor(confidence=0.95),
    ).extract_invoice(invoice.id)

    updated = db_session.get(Invoice, invoice.id)
    assert result.status == InvoiceStatus.EXTRACTED
    assert updated.status == InvoiceStatus.EXTRACTED
    assert updated.vendor_name == "Acme Supplies"
    assert updated.amount == "110.00"
    assert updated.subtotal == "100.00"
    assert updated.tax_amount == "10.00"
    assert updated.invoice_date == "2026-06-17"
    assert updated.due_date == "2026-07-17"
    assert updated.currency == "USD"
    assert updated.po_reference == "PO-42"
    assert updated.extraction_confidence == "0.95"

    line_items = db_session.query(LineItem).filter(LineItem.invoice_id == invoice.id).all()
    assert len(line_items) == 1
    assert line_items[0].description == "Paper"
    assert line_items[0].confidence == "0.91"


def test_extract_invoice_routes_low_confidence_to_review(db_session, tmp_path):
    invoice = create_invoice(db_session, tmp_path)

    result = ExtractionService(
        InvoiceRepository(db_session),
        extractor=FakeExtractor(confidence=0.51),
        confidence_threshold=0.75,
    ).extract_invoice(invoice.id)

    updated = db_session.get(Invoice, invoice.id)
    assert result.status == InvoiceStatus.NEEDS_REVIEW
    assert updated.status == InvoiceStatus.NEEDS_REVIEW


def test_extract_invoice_marks_failed_when_extractor_errors(db_session, tmp_path):
    invoice = create_invoice(db_session, tmp_path)

    with pytest.raises(ExtractionError, match="OCR failed"):
        ExtractionService(
            InvoiceRepository(db_session),
            extractor=FailingExtractor(),
        ).extract_invoice(invoice.id)

    updated = db_session.get(Invoice, invoice.id)
    assert updated.status == InvoiceStatus.FAILED
    assert updated.extraction_error == "OCR failed"


def test_extraction_schema_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        InvoiceExtraction(
            overall_confidence=1.1,
            field_confidence={"total_amount": 0.9},
        )
