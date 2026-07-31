from app.modules.inventory.dtoes.dtos import ConfirmOutcome, ReserveOutcome
from app.modules.inventory.models.inventory_product import InventoryProvider
from app.modules.inventory.providers.provider_registry import ProviderRegistry
from app.modules.inventory.providers.interfaces.capabilities import (
    StockCheckable,
    Reservable,
)
from app.modules.inventory.dtoes.dtos import ProviderStockResult


class ProviderService:
    """
    Single entry point for all provider interactions. Callers (ReservationItemReserver,
    ReservationService) never touch ProviderRegistry or the capability interfaces
    directly — they call this facade and get back a uniform, provider-agnostic result.
    """

    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry

    def check_stock(self, provider: InventoryProvider, sku: str) -> ProviderStockResult:
        client = self.provider_registry.get_client(provider)
        if not isinstance(client, StockCheckable):
            return ProviderStockResult(
                success=False, error_message="provider does not support stock checks"
            )
        return client.check_stock(sku)

    def reserve(
        self, provider: InventoryProvider, sku: str, quantity: int, idempotency_key: str
    ) -> ReserveOutcome:
        client = self.provider_registry.get_client(provider)

        if not isinstance(client, Reservable):
            return ReserveOutcome(
                success=True, provider_reservation_ref=None, upstream_reserved=False
            )

        result = client.reserve(sku, quantity, idempotency_key)
        return ReserveOutcome(
            success=result.success,
            provider_reservation_ref=result.provider_reservation_ref,
            upstream_reserved=result.success,
            error_message=result.error_message,
        )

    def confirm(
        self,
        provider: InventoryProvider,
        provider_reservation_ref: str | None,
        idempotency_key: str,
    ) -> ConfirmOutcome:
        client = self.provider_registry.get_client(provider)

        if not isinstance(client, Reservable) or provider_reservation_ref is None:
            return ConfirmOutcome(success=True)

        result = client.confirm(provider_reservation_ref, idempotency_key)
        return ConfirmOutcome(
            success=result.success, error_message=result.error_message
        )

    def release(
        self, provider: InventoryProvider, provider_reservation_ref: str | None
    ) -> None:
        client = self.provider_registry.get_client(provider)
        if isinstance(client, Reservable) and provider_reservation_ref:
            client.release(provider_reservation_ref)

    def revalidate_stock(
        self, provider: InventoryProvider, sku: str, required_quantity: int
    ) -> bool:
        """
        Used at confirm time for providers with no upstream hold (StockCheckable only),
        as a last-moment safety check since we can't guarantee exclusivity with them.
        """
        result = self.check_stock(provider, sku)
        if not result.success:
            return False
        if result.qty_available is None:
            return True
        return result.qty_available >= required_quantity
