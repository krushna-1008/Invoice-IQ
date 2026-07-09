import hmac
from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    api_key_hash: str


def _configured_keys() -> dict[str, str]:
    keys: dict[str, str] = {}
    for pair in settings.api_keys.split(","):
        if not pair.strip() or ":" not in pair:
            continue
        tenant_id, api_key = pair.split(":", 1)
        keys[tenant_id.strip()] = api_key.strip()
    return keys


def hash_secret(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def get_auth_context(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthContext:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key header is required")

    for tenant_id, configured_key in _configured_keys().items():
        if hmac.compare_digest(x_api_key, configured_key):
            return AuthContext(tenant_id=tenant_id, api_key_hash=hash_secret(configured_key))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_tenant(auth: AuthContext, tenant_id: str) -> None:
    if auth.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant access denied")
