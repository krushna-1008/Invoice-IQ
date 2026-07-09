import json
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Invoice, Vendor


class CacheService:
    _memory_cache: dict[str, str] = {}

    def __init__(self, redis_url: str = settings.redis_url) -> None:
        self.redis = None
        try:
            import redis

            self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
        except Exception:
            self.redis = None

    def get_json(self, key: str) -> dict | None:
        value = self.redis.get(key) if self.redis else self._memory_cache.get(key)
        return json.loads(value) if value else None

    def set_json(self, key: str, value: dict, ttl_seconds: int = 300) -> None:
        encoded = json.dumps(value)
        if self.redis:
            self.redis.setex(key, ttl_seconds, encoded)
        else:
            self._memory_cache[key] = encoded


class VendorIntelligenceService:
    def __init__(self, db: Session, cache: CacheService | None = None) -> None:
        self.db = db
        self.cache = cache or CacheService()

    def vendor_profile(self, tenant_id: str, vendor_id: str) -> dict:
        key = f"vendor-profile:{tenant_id}:{vendor_id}"
        cached = self.cache.get_json(key)
        if cached:
            return cached

        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.tenant_id == tenant_id, Vendor.id == vendor_id)
            .first()
        )
        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.tenant_id == tenant_id, Invoice.vendor_id == vendor_id)
            .all()
        )
        total_spend = sum((self._money(invoice.amount) or Decimal("0")) for invoice in invoices)
        profile = {
            "tenant_id": tenant_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor.name if vendor else None,
            "invoice_count": len(invoices),
            "total_spend": str(total_spend),
        }
        self.cache.set_json(key, profile)
        return profile

    @staticmethod
    def _money(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value.replace(",", "").replace("$", "").strip())
        except InvalidOperation:
            return None
