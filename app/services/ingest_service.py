import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.models import Invoice, InvoiceStatus
from app.repositories.invoice_repository import DuplicateInvoiceError, InvoiceRepository
from app.workers.extraction_worker import enqueue_extraction

UPLOAD_DIR = Path("storage/invoices")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class IngestService:
    def __init__(self, repository: InvoiceRepository) -> None:
        self.repository = repository

    async def ingest_upload(
        self,
        file: UploadFile,
        tenant_id: str,
        vendor_id: str,
        invoice_number: str,
    ) -> dict[str, str | bool]:
        self._validate_metadata(tenant_id, vendor_id, invoice_number)
        self._validate_file(file)

        contents = await file.read()
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invoice file is required",
            )
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Invoice file exceeds 20MB limit",
            )

        invoice_id = str(uuid4())
        file_hash = hashlib.sha256(contents).hexdigest()
        file_path = self._store_file(tenant_id, invoice_id, contents)

        self.repository.ensure_tenant(tenant_id)
        self.repository.ensure_vendor(tenant_id, vendor_id)

        invoice = Invoice(
            id=invoice_id,
            tenant_id=tenant_id,
            vendor_id=vendor_id,
            invoice_number=invoice_number,
            file_path=str(file_path),
            file_hash=file_hash,
            storage_location="local",
            status=InvoiceStatus.RECEIVED,
        )

        try:
            created = self.repository.create_invoice(invoice)
        except DuplicateInvoiceError as exc:
            file_path.unlink(missing_ok=True)
            if exc.invoice is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice already exists",
                ) from exc
            return {
                "invoice_id": exc.invoice.id,
                "status": "duplicate",
                "duplicate": True,
            }

        enqueue_extraction(created.id)
        self.repository.update_status(created, InvoiceStatus.QUEUED)
        return {
            "invoice_id": created.id,
            "status": "received",
            "duplicate": False,
        }

    def queue_existing_invoice(self, invoice_id: str) -> dict[str, str]:
        invoice = self.repository.get(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        enqueue_extraction(invoice.id)
        updated = self.repository.update_status(invoice, InvoiceStatus.QUEUED)
        return {"invoice_id": updated.id, "status": updated.status}

    @staticmethod
    def _validate_metadata(tenant_id: str, vendor_id: str, invoice_number: str) -> None:
        missing = [
            field_name
            for field_name, value in {
                "tenant_id": tenant_id,
                "vendor_id": vendor_id,
                "invoice_number": invoice_number,
            }.items()
            if not value.strip()
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing required metadata: {', '.join(missing)}",
            )

    @staticmethod
    def _validate_file(file: UploadFile) -> None:
        if file.content_type not in {"application/pdf", "application/octet-stream"}:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PDF invoice uploads are supported",
            )

    @staticmethod
    def _store_file(tenant_id: str, invoice_id: str, contents: bytes) -> Path:
        tenant_dir = UPLOAD_DIR / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        file_path = tenant_dir / f"{invoice_id}.pdf"
        file_path.write_bytes(contents)
        return file_path

