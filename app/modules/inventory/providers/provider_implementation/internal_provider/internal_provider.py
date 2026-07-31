import uuid

from app.modules.inventory.dtoes.dtos import ProviderReserveResult, ProviderStockResult
from app.modules.inventory.models.inventory_provider import InventoryProvider
from app.modules.inventory.providers.interfaces.capabilities import (
    Reservable,
    StockCheckable,
)

__all__ = ["InternalProviderClient"]


class InternalProviderClient(StockCheckable, Reservable):
    """
    Platform's own warehouse. ProductInventory in our own DB is already the
    source of truth, so there's no external system to call — every method
    here is a trivial local operation, mostly to satisfy the interface
    uniformly across all provider types.
    """

    def __init__(self, provider: InventoryProvider):
        self.provider = provider

    def check_stock(self, sku: str) -> ProviderStockResult:
        return ProviderStockResult(success=True, qty_available=None)

    def reserve(
        self, sku: str, quantity: int, idempotency_key: str
    ) -> ProviderReserveResult:
        return ProviderReserveResult(
            success=True, provider_reservation_ref=str(uuid.uuid4())
        )

    def confirm(
        self, provider_reservation_ref: str, idempotency_key: str
    ) -> ProviderReserveResult:
        return ProviderReserveResult(
            success=True, provider_reservation_ref=provider_reservation_ref
        )

    def release(self, provider_reservation_ref: str) -> ProviderReserveResult:
        return ProviderReserveResult(
            success=True, provider_reservation_ref=provider_reservation_ref
        )
