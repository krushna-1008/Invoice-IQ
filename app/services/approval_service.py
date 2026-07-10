import hmac
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Approval, Invoice
from app.schemas.approval import ApprovalResponse, ApprovalRouteResponse
from app.services.audit_service import AuditService


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def route_invoice(self, invoice_id: str) -> ApprovalRouteResponse:
        invoice = self.db.get(Invoice, invoice_id)
        if invoice is None:
            raise ValueError("Invoice not found")

        amount = self._money(invoice.amount)
        if amount is not None and amount < Decimal("500"):
            route = "AUTO_APPROVED"
            approvals = [self._create_approval(invoice, approver_id=None, status="APPROVED")]
        elif amount is not None and amount <= Decimal("5000"):
            route = "SINGLE_APPROVER"
            approvals = [
                self._create_approval(invoice, approver_id="ap-manager", status="PENDING"),
            ]
        else:
            route = "DUAL_APPROVER"
            approvals = [
                self._create_approval(invoice, approver_id="ap-manager", status="PENDING"),
                self._create_approval(invoice, approver_id="finance-controller", status="PENDING"),
            ]

        AuditService(self.db).record(
            tenant_id=invoice.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action=f"approval_route:{route}",
        )
        self.db.commit()
        return ApprovalRouteResponse(
            invoice_id=invoice.id,
            route=route,
            approvals=[self._response(approval) for approval in approvals],
        )

    def decide(self, approval_id: str, decision: str, actor_id: str | None = None) -> ApprovalResponse:
        approval = self.db.get(Approval, approval_id)
        if approval is None:
            raise ValueError("Approval not found")
        return self._decide_approval(approval, decision, actor_id=actor_id)

    def decide_with_token(self, token: str, decision: str) -> ApprovalResponse:
        approval_id = self._approval_id_from_token(token)
        approval = self.db.get(Approval, approval_id)
        if approval is None:
            raise ValueError("Approval not found")
        if not approval.token_hash or not hmac.compare_digest(approval.token_hash, self._hash_token(token)):
            raise ValueError("Invalid approval token")
        expires_at = approval.token_expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at and expires_at < datetime.now(UTC):
            raise ValueError("Approval token expired")
        return self._decide_approval(approval, decision, actor_id=approval.approver_id, token_used=True)

    def _decide_approval(
        self,
        approval: Approval,
        decision: str,
        actor_id: str | None = None,
        token_used: bool = False,
    ) -> ApprovalResponse:
        normalized = decision.upper()
        if normalized not in {"APPROVED", "REJECTED"}:
            raise ValueError("Decision must be APPROVED or REJECTED")
        if approval.status in {"APPROVED", "REJECTED"}:
            return self._response(approval)
        approval.status = normalized
        approval.decided_at = datetime.now(UTC)
        if token_used:
            approval.token_used_at = approval.decided_at
        AuditService(self.db).record(
            tenant_id=approval.tenant_id,
            entity_type="approval",
            entity_id=approval.id,
            action=f"approval:{normalized}",
            actor_id=actor_id,
        )
        self.db.commit()
        self.db.refresh(approval)
        return self._response(approval)

    def _create_approval(self, invoice: Invoice, approver_id: str | None, status: str) -> Approval:
        approval = Approval(
            id=str(uuid4()),
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            approver_id=approver_id,
            status=status,
        )
        if status == "PENDING":
            token = self._sign_token(approval.id)
            approval.token_hash = self._hash_token(token)
            approval.token_expires_at = datetime.now(UTC) + timedelta(hours=settings.approval_token_ttl_hours)
        self.db.add(approval)
        self.db.flush()
        return approval

    def _response(self, approval: Approval) -> ApprovalResponse:
        response = ApprovalResponse.model_validate(approval)
        if approval.status == "PENDING":
            response.approval_token = self._sign_token(approval.id)
        return response

    @staticmethod
    def _sign_token(approval_id: str) -> str:
        signature = hmac.new(
            settings.approval_token_secret.encode("utf-8"),
            approval_id.encode("utf-8"),
            sha256,
        ).hexdigest()
        return f"{approval_id}.{signature}"

    @staticmethod
    def _hash_token(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _approval_id_from_token(token: str) -> str:
        if "." not in token:
            raise ValueError("Invalid approval token")
        approval_id, signature = token.rsplit(".", 1)
        expected = hmac.new(
            settings.approval_token_secret.encode("utf-8"),
            approval_id.encode("utf-8"),
            sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid approval token")
        return approval_id

    @staticmethod
    def _money(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value.replace(",", "").replace("$", "").strip())
        except InvalidOperation:
            return None
