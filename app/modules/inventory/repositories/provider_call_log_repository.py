from datetime import datetime
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db_postgres
from app.modules.inventory.models.provider_call_log import (
    ProviderCallLog,
    ProviderCallType,
    ProviderCallOutcome,
)

__all__ = ["ProviderCallLogRepository", "get_provider_call_log_repository"]


class ProviderCallLogRepository:
    """Persists an audit trail of every provider call attempt — success and failure alike."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        provider_id: int,
        call_type: ProviderCallType,
        outcome: ProviderCallOutcome,
        attempted_at: datetime,
        latency_ms: int | None = None,
        reservation_item_id: int | None = None,
        request_payload: dict | None = None,
        response_payload: dict | None = None,
        error_message: str | None = None,
    ) -> ProviderCallLog:
        entry = ProviderCallLog(
            provider_id=provider_id,
            reservation_item_id=reservation_item_id,
            call_type=call_type,
            outcome=outcome,
            request_payload=request_payload,
            response_payload=response_payload,
            error_message=error_message,
            latency_ms=latency_ms,
            attempted_at=attempted_at,
        )
        self.db.add(entry)
        self.db.flush()
        return entry


def get_provider_call_log_repository(
    db: Session = Depends(get_db_postgres),
) -> ProviderCallLogRepository:
    return ProviderCallLogRepository(db)
