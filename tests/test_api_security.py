from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.postgres import Base
from app.main import app
from app.models import Invoice, InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.api.invoices import get_db


def test_upload_requires_api_key(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/invoices",
            data={"tenant_id": "tenant-1", "vendor_id": "vendor-1", "invoice_number": "INV-1"},
            files={"file": ("invoice.pdf", b"%PDF-1.7 sample", "application/pdf")},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_tenant_api_key_cannot_read_other_tenant_invoice():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    setup_db = session_factory()
    repository = InvoiceRepository(setup_db)
    repository.ensure_tenant("demo-tenant")
    repository.ensure_vendor("demo-tenant", "vendor-1")
    invoice = Invoice(
        id="invoice-1",
        tenant_id="demo-tenant",
        vendor_id="vendor-1",
        invoice_number="INV-1",
        file_path=str(Path("storage") / "invoice.pdf"),
        file_hash="hash",
        storage_location="local",
        status=InvoiceStatus.RECEIVED,
    )
    repository.create_invoice(invoice)
    setup_db.close()

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/v1/invoices/invoice-1", headers={"X-API-Key": "dev-secret"})
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
