import enum
from datetime import datetime
from sqlalchemy import String, Integer, Enum, ForeignKey, DateTime, JSON, Float
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.utils.base_model import BaseModel

__all__ = ["ProviderCallLog", "ProviderCallType", "ProviderCallOutcome"]


class ProviderCallType(str, enum.Enum):
    CHECK_STOCK = "check_stock"
    RESERVE = "reserve"
    CONFIRM = "confirm"
    RELEASE = "release"


class ProviderCallOutcome(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    STALE_DATA = "stale_data"


class ProviderCallLog(BaseModel):
    __tablename__ = "provider_call_logs"

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_providers.id"), nullable=False
    )
    reservation_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservation_items.id"), nullable=True
    )

    call_type: Mapped[ProviderCallType] = mapped_column(
        Enum(ProviderCallType), nullable=False
    )
    outcome: Mapped[ProviderCallOutcome] = mapped_column(
        Enum(ProviderCallOutcome), nullable=False
    )

    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    provider: Mapped["InventoryProvider"] = relationship()
    reservation_item: Mapped["ReservationItem | None"] = relationship()
