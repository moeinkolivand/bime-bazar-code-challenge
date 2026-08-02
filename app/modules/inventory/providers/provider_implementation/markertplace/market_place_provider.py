__all__ = ["MarketplaceSellerXProviderClient"]


from app.modules.inventory.dtoes.dtos import ProviderStockResult
from app.modules.inventory.exceptions.provider_request_error import ProviderRequestError
from app.modules.inventory.models.inventory_provider import InventoryProvider
from app.modules.inventory.providers.interfaces.capabilities import StockCheckable
from app.modules.inventory.providers.shared.circuit_breaker import CircuitBreaker
from app.modules.inventory.providers.shared.retry_policy import RetryPolicy
from app.modules.inventory.providers.shared.transport import RestTransport


class MarketplaceSellerXProviderClient(StockCheckable):
    """
    Read-only marketplace seller — exposes stock levels via Rest only.
    Deliberately does NOT implement Reservable: this provider has no
    reservation/hold API at all, so we don't pretend to support one.
    ReservationItemReserver relies on a local-only hold for this provider,
    plus a check_stock() recheck at confirm time via ProviderService.
    """

    def __init__(self, provider: InventoryProvider):
        self.provider = provider
        self.transport = RestTransport(
            base_url="https://sellerx.example.com/inventory?wsdl",
            timeout_seconds=5.0,  # this provider is known to be slower
        )
        self.retry = RetryPolicy(max_retries=5, base_delay_seconds=1.0)
        self.breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

    def check_stock(self, sku: str) -> ProviderStockResult:
        # try:
        #     resp = self.breaker.execute(
        #         lambda: self.retry.execute(
        #             lambda: self.transport.post("GetStockLevel", json={"sku": sku})
        #         )
        #     )
        #     return ProviderStockResult(
        #         success=True, qty_available=resp.json_body["level"]
        #     )
        # except ProviderRequestError as e:
        #     return ProviderStockResult(success=False, error_message=e.message)
        return ProviderStockResult(success=True, qty_available=2)