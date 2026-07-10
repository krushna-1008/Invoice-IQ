import base64
import io
import json
import re
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.models import Invoice, InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.extraction import ExtractionResult, InvoiceExtraction


class ExtractionError(Exception):
    pass


class InvoiceExtractor(Protocol):
    def extract(self, file_path: Path) -> InvoiceExtraction:
        ...


class PDFImageRenderer:
    def __init__(self, max_pages: int = settings.max_pdf_pages) -> None:
        self.max_pages = max_pages

    def render_png_pages(self, file_path: Path) -> list[bytes]:
        try:
            from pdf2image import convert_from_path
        except ImportError as exc:
            raise ExtractionError("pdf2image is not installed") from exc

        try:
            images = convert_from_path(
                str(file_path),
                dpi=150,
                fmt="png",
                first_page=1,
                last_page=self.max_pages,
            )
        except Exception as exc:
            raise ExtractionError(
                "Unable to render PDF pages. Install Poppler and ensure the file is a valid PDF."
            ) from exc

        rendered_pages: list[bytes] = []
        for image in images:
            rendered = io.BytesIO()
            image.save(rendered, format="PNG", optimize=True)
            rendered_pages.append(rendered.getvalue())
        return rendered_pages


class ClaudeVisionInvoiceExtractor:
    def __init__(
        self,
        api_key: str | None = settings.anthropic_api_key,
        model: str | None = settings.anthropic_model,
        renderer: PDFImageRenderer | None = None,
    ) -> None:
        if not api_key:
            raise ExtractionError("ANTHROPIC_API_KEY is required for Claude extraction")
        if not model:
            raise ExtractionError("ANTHROPIC_MODEL is required for Claude extraction")
        try:
            import anthropic
        except ImportError as exc:
            raise ExtractionError("anthropic is not installed") from exc

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.renderer = renderer or PDFImageRenderer()

    def extract(self, file_path: Path) -> InvoiceExtraction:
        image_blocks = self._image_blocks(file_path)
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        *image_blocks,
                        {"type": "text", "text": self._prompt()},
                    ],
                }
            ],
        )
        text = self._message_text(message)
        return InvoiceExtraction.model_validate_json(self._extract_json(text))

    def _image_blocks(self, file_path: Path) -> list[dict]:
        if file_path.suffix.lower() != ".pdf":
            data = file_path.read_bytes()
            media_type = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
            return [self._image_block(data, media_type)]

        pages = self.renderer.render_png_pages(file_path)
        if not pages:
            raise ExtractionError("PDF did not render any pages")
        return [self._image_block(page, "image/png") for page in pages]

    @staticmethod
    def _image_block(data: bytes, media_type: str) -> dict:
        encoded = base64.standard_b64encode(data).decode("utf-8")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        }

    @staticmethod
    def _message_text(message) -> str:
        parts: list[str] = []
        for block in getattr(message, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ExtractionError("Claude response did not contain JSON")
        json.loads(match.group(0))
        return match.group(0)

    @staticmethod
    def _prompt() -> str:
        return (
            "Extract the invoice into strict JSON only. Do not include markdown. "
            "Schema: vendor_name, invoice_number, invoice_date, due_date, currency, "
            "subtotal, tax_amount, total_amount, po_reference, line_items, "
            "field_confidence, overall_confidence. Dates should be ISO-8601 when visible. "
            "Amounts should be strings preserving the document value. line_items must contain "
            "description, quantity, unit_price, tax_amount, total_amount, confidence. "
            "Every confidence value must be between 0 and 1."
        )


class ExtractionService:
    def __init__(
        self,
        repository: InvoiceRepository,
        extractor: InvoiceExtractor | None = None,
        confidence_threshold: float = settings.extraction_confidence_threshold,
    ) -> None:
        self.repository = repository
        self.extractor = extractor
        self.confidence_threshold = confidence_threshold

    def extract_invoice(self, invoice_id: str, mark_failed_on_error: bool = True) -> ExtractionResult:
        invoice = self.repository.get(invoice_id)
        if invoice is None:
            raise ExtractionError("Invoice not found")

        self.repository.update_status(invoice, InvoiceStatus.EXTRACTING)
        try:
            extraction = self._extractor().extract(Path(invoice.file_path))
            final_status = (
                InvoiceStatus.EXTRACTED
                if extraction.overall_confidence >= self.confidence_threshold
                else InvoiceStatus.NEEDS_REVIEW
            )
            updated = self.repository.persist_extraction(invoice, extraction, final_status)
            return ExtractionResult(
                invoice_id=updated.id,
                status=updated.status,
                confidence=extraction.overall_confidence,
                line_item_count=len(extraction.line_items),
            )
        except Exception as exc:
            if mark_failed_on_error:
                self.repository.mark_failed(invoice, str(exc))
            raise

    def _extractor(self) -> InvoiceExtractor:
        if self.extractor is None:
            self.extractor = ClaudeVisionInvoiceExtractor()
        return self.extractor
