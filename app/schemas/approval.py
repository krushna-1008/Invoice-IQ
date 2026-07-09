from pydantic import BaseModel, ConfigDict


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    approver_id: str | None
    status: str
    approval_token: str | None = None


class ApprovalRouteResponse(BaseModel):
    invoice_id: str
    route: str
    approvals: list[ApprovalResponse]
