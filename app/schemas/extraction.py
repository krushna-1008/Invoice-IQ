from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractedLineItem(BaseModel):
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    tax_amount: str | None = None
    total_amount: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    tax_amount: str | None = None
    total_amount: str | None = None
    po_reference: str | None = None
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("field_confidence")
    @classmethod
    def validate_field_confidence(cls, value: dict[str, float]) -> dict[str, float]:
        for field, confidence in value.items():
            if confidence < 0.0 or confidence > 1.0:
                raise ValueError(f"Confidence for {field} must be between 0 and 1")
        return value


class ExtractionResult(BaseModel):
    invoice_id: str
    status: str
    confidence: float | None = None
    line_item_count: int = 0
