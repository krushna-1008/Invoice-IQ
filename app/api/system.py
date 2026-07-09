from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.models import Approval, Invoice

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> Response:
    invoice_count = db.query(Invoice).count()
    pending_approvals = db.query(Approval).filter(Approval.status == "PENDING").count()
    body = "\n".join(
        [
            "# HELP invoiceiq_invoices_total Total invoices stored.",
            "# TYPE invoiceiq_invoices_total gauge",
            f"invoiceiq_invoices_total {invoice_count}",
            "# HELP invoiceiq_pending_approvals_total Pending approvals.",
            "# TYPE invoiceiq_pending_approvals_total gauge",
            f"invoiceiq_pending_approvals_total {pending_approvals}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")
