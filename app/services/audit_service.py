from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str | None = None,
        details: str | None = None,
    ) -> AuditLog:
        event = AuditLog(
            id=str(uuid4()),
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            details=details,
        )
        self.db.add(event)
        self.db.flush()
        return event

