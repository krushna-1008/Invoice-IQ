from collections import deque

from app.core.config import settings
from app.db.postgres import SessionLocal
from app.models import InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.services.extraction_service import ExtractionService
from app.workers.celery_app import celery_app

queued_extraction_jobs: deque[dict[str, str]] = deque()


def enqueue_extraction(invoice_id: str) -> None:
    payload = {"invoice_id": invoice_id}
    queued_extraction_jobs.append(payload)
    if not settings.celery_queue_enabled:
        payload["queue_mode"] = "local"
        return
    try:
        extract_invoice.delay(invoice_id)
    except Exception as exc:
        payload["queue_error"] = str(exc)


@celery_app.task(
    bind=True,
    name="invoiceiq.extract_invoice",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def extract_invoice(self, invoice_id: str) -> dict:
    db = SessionLocal()
    repository = InvoiceRepository(db)
    try:
        result = ExtractionService(repository).extract_invoice(invoice_id, mark_failed_on_error=False)
        return result.model_dump()
    except Exception as exc:
        invoice = repository.get(invoice_id)
        max_retries = getattr(self, "max_retries", 3) or 3
        if invoice is not None and self.request.retries >= max_retries:
            repository.mark_failed(invoice, str(exc))
        elif invoice is not None:
            repository.update_status(invoice, InvoiceStatus.QUEUED)
        raise
    finally:
        db.close()
