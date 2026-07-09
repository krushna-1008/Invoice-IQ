from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.core.security import AuthContext, get_auth_context, require_tenant
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceCreateResponse, InvoiceDetailResponse, QueueResponse
from app.schemas.extraction import ExtractionResult
from app.services.ingest_service import IngestService
from app.services.extraction_service import ExtractionService
from app.services.matching_service import MatchingService
from app.schemas.matching import MatchResultResponse
from app.services.approval_service import ApprovalService
from app.schemas.approval import ApprovalResponse, ApprovalRouteResponse
from app.services.cache_service import VendorIntelligenceService
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["invoices"])


def get_ingest_service(db: Annotated[Session, Depends(get_db)]) -> IngestService:
    return IngestService(InvoiceRepository(db))


@router.post(
    "/invoices",
    response_model=InvoiceCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_invoice(
    service: Annotated[IngestService, Depends(get_ingest_service)],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    file: Annotated[UploadFile, File(...)],
    tenant_id: Annotated[str, Form(...)],
    vendor_id: Annotated[str, Form(...)],
    invoice_number: Annotated[str, Form(...)],
):
    require_tenant(auth, tenant_id)
    result = await service.ingest_upload(
        file=file,
        tenant_id=tenant_id,
        vendor_id=vendor_id,
        invoice_number=invoice_number,
    )
    return result


@router.post(
    "/webhooks/invoices",
    response_model=InvoiceCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_invoice_webhook(
    service: Annotated[IngestService, Depends(get_ingest_service)],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    file: Annotated[UploadFile, File(...)],
    tenant_id: Annotated[str, Form(...)],
    vendor_id: Annotated[str, Form(...)],
    invoice_number: Annotated[str, Form(...)],
):
    return await upload_invoice(service, auth, file, tenant_id, vendor_id, invoice_number)


@router.post(
    "/email/invoices",
    response_model=InvoiceCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_invoice_email_forward(
    service: Annotated[IngestService, Depends(get_ingest_service)],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    file: Annotated[UploadFile, File(...)],
    tenant_id: Annotated[str, Form(...)],
    vendor_id: Annotated[str, Form(...)],
    invoice_number: Annotated[str, Form(...)],
):
    return await upload_invoice(service, auth, file, tenant_id, vendor_id, invoice_number)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(
    invoice_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    invoice = InvoiceRepository(db).get(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    require_tenant(auth, invoice.tenant_id)
    return invoice


@router.post("/invoices/{invoice_id}/extract", response_model=QueueResponse)
def queue_invoice_extraction(
    invoice_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[IngestService, Depends(get_ingest_service)],
    db: Annotated[Session, Depends(get_db)],
):
    invoice = InvoiceRepository(db).get(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    require_tenant(auth, invoice.tenant_id)
    return service.queue_existing_invoice(invoice_id)


@router.post("/invoices/{invoice_id}/extract-now", response_model=ExtractionResult)
def extract_invoice_now(
    invoice_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    invoice = InvoiceRepository(db).get(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    require_tenant(auth, invoice.tenant_id)
    return ExtractionService(InvoiceRepository(db)).extract_invoice(invoice_id)


@router.post("/invoices/{invoice_id}/match", response_model=MatchResultResponse)
def match_invoice(
    invoice_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        invoice = InvoiceRepository(db).get(invoice_id)
        if invoice is None:
            raise ValueError("Invoice not found")
        require_tenant(auth, invoice.tenant_id)
        return MatchingService(db).match_invoice(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/invoices/{invoice_id}/route-approval", response_model=ApprovalRouteResponse)
def route_invoice_approval(
    invoice_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        invoice = InvoiceRepository(db).get(invoice_id)
        if invoice is None:
            raise ValueError("Invoice not found")
        require_tenant(auth, invoice.tenant_id)
        return ApprovalService(db).route_invoice(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/{decision}", response_model=ApprovalResponse)
def decide_approval(
    approval_id: str,
    decision: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return ApprovalService(db).decide(approval_id, decision, actor_id=auth.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/approval-links/{token}/{decision}", response_model=ApprovalResponse)
def decide_approval_by_token(
    token: str,
    decision: str,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return ApprovalService(db).decide_with_token(token, decision)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/tenants/{tenant_id}/vendors/{vendor_id}/profile")
def get_vendor_profile(
    tenant_id: str,
    vendor_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    require_tenant(auth, tenant_id)
    return VendorIntelligenceService(db).vendor_profile(tenant_id, vendor_id)


@router.get("/tenants/{tenant_id}/analytics/weekly-spend")
def weekly_spend_summary(
    tenant_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
):
    require_tenant(auth, tenant_id)
    return AnalyticsService(db).weekly_spend_summary(tenant_id)
