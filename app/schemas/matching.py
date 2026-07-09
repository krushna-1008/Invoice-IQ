from pydantic import BaseModel, ConfigDict


class DiscrepancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: str
    message: str


class MatchResultResponse(BaseModel):
    invoice_id: str
    status: str
    purchase_order_id: str | None = None
    discrepancies: list[DiscrepancyResponse]

