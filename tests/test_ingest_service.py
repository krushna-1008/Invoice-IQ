from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import UploadFile

from app.db.postgres import Base
from app.models import Invoice, InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.services import ingest_service
from app.services.ingest_service import IngestService


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


@pytest.fixture()
def storage_dir(tmp_path, monkeypatch):
    upload_dir = tmp_path / "storage" / "invoices"
    monkeypatch.setattr(ingest_service, "UPLOAD_DIR", upload_dir)
    return upload_dir


def make_upload(filename: str = "invoice.pdf") -> UploadFile:
    path = Path(filename)
    return UploadFile(
        filename=path.name,
        file=path.open("wb+"),
        headers={"content-type": "application/pdf"},
    )


@pytest.mark.asyncio
async def test_ingest_upload_creates_invoice_and_queues_extraction(db_session, storage_dir):
    service = IngestService(InvoiceRepository(db_session))
    upload = UploadFile(
        filename="invoice.pdf",
        file=__import__("io").BytesIO(b"%PDF-1.7 sample"),
        headers={"content-type": "application/pdf"},
    )

    result = await service.ingest_upload(
        file=upload,
        tenant_id="tenant-1",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
    )

    invoice = db_session.query(Invoice).one()
    assert result == {"invoice_id": invoice.id, "status": "received", "duplicate": False}
    assert invoice.tenant_id == "tenant-1"
    assert invoice.vendor_id == "vendor-1"
    assert invoice.invoice_number == "INV-1001"
    assert invoice.status == InvoiceStatus.QUEUED
    assert Path(invoice.file_path).exists()


@pytest.mark.asyncio
async def test_ingest_upload_is_idempotent_by_tenant_vendor_and_invoice_number(db_session, storage_dir):
    service = IngestService(InvoiceRepository(db_session))

    first = await service.ingest_upload(
        file=UploadFile(
            filename="invoice.pdf",
            file=__import__("io").BytesIO(b"%PDF-1.7 original"),
            headers={"content-type": "application/pdf"},
        ),
        tenant_id="tenant-1",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
    )
    second = await service.ingest_upload(
        file=UploadFile(
            filename="invoice.pdf",
            file=__import__("io").BytesIO(b"%PDF-1.7 retry"),
            headers={"content-type": "application/pdf"},
        ),
        tenant_id="tenant-1",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
    )

    assert second == {"invoice_id": first["invoice_id"], "status": "duplicate", "duplicate": True}
    assert db_session.query(Invoice).count() == 1


@pytest.mark.asyncio
async def test_idempotency_is_scoped_per_tenant(db_session, storage_dir):
    service = IngestService(InvoiceRepository(db_session))

    first = await service.ingest_upload(
        file=UploadFile(
            filename="invoice.pdf",
            file=__import__("io").BytesIO(b"%PDF-1.7 tenant one"),
            headers={"content-type": "application/pdf"},
        ),
        tenant_id="tenant-1",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
    )
    second = await service.ingest_upload(
        file=UploadFile(
            filename="invoice.pdf",
            file=__import__("io").BytesIO(b"%PDF-1.7 tenant two"),
            headers={"content-type": "application/pdf"},
        ),
        tenant_id="tenant-2",
        vendor_id="vendor-1",
        invoice_number="INV-1001",
    )

    assert first["invoice_id"] != second["invoice_id"]
    assert db_session.query(Invoice).count() == 2
