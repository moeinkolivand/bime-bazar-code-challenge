
__all__ = ["WarehouseProviderClient"]


from app.modules.inventory.dtoes.dtos import ProviderReserveResult, ProviderStockResult
from app.modules.inventory.exceptions.provider_request_error import ProviderRequestError
from app.modules.inventory.models.inventory_provider import InventoryProvider
from app.modules.inventory.providers.interfaces.capabilities import Reservable, StockCheckable
from app.modules.inventory.providers.shared.circuit_breaker import CircuitBreaker
from app.modules.inventory.providers.shared.retry_policy import RetryPolicy
from app.modules.inventory.providers.shared.transport import RestTransport


class WarehouseProviderClient(StockCheckable, Reservable):
    """
    Full-capability external provider — REST API, supports check/reserve/confirm/release.
    Owns its own auth, transport, retry, and breaker configuration entirely.
    """

    def __init__(self, provider: InventoryProvider):
        self.provider = provider
        auth = self._resolve_api_key(provider.credentials_ref)
        self.transport = RestTransport(
            base_url="https://warehouse-provider.example.com",
            timeout_seconds=3.0,
        )
        self.retry = RetryPolicy(max_retries=3, base_delay_seconds=0.5)
        self.breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)

    def _resolve_api_key(self, credentials_ref: str | None) -> str:
        return "resolved-api-key"

    def _call(self, fn):
        return self.breaker.execute(lambda: self.retry.execute(fn))

    def check_stock(self, sku: str) -> ProviderStockResult:
        try:
            resp = self._call(lambda: self.transport.get(f"/stock/{sku}"))
            return ProviderStockResult(success=True, qty_available=resp.json_body["qty_available"])
        except ProviderRequestError as e:
            return ProviderStockResult(success=False, error_message=e.message)

    def reserve(self, sku: str, quantity: int, idempotency_key: str) -> ProviderReserveResult:
        try:
            resp = self._call(lambda: self.transport.post(
                "/reserve",
                json={"sku": sku, "quantity": quantity, "idempotency_key": idempotency_key},
            ))
            return ProviderReserveResult(success=True, provider_reservation_ref=resp.json_body["reservation_id"])
        except ProviderRequestError as e:
            return ProviderReserveResult(success=False, error_message=e.message)

    def confirm(self, provider_reservation_ref: str, idempotency_key: str) -> ProviderReserveResult:
        try:
            self._call(lambda: self.transport.post(
                f"/reserve/{provider_reservation_ref}/confirm",
                json={"idempotency_key": idempotency_key},
            ))
            return ProviderReserveResult(success=True, provider_reservation_ref=provider_reservation_ref)
        except ProviderRequestError as e:
            return ProviderReserveResult(
                success=False, provider_reservation_ref=provider_reservation_ref, error_message=e.message
            )

    def release(self, provider_reservation_ref: str) -> ProviderReserveResult:
        try:
            self._call(lambda: self.transport.post(f"/reserve/{provider_reservation_ref}/release"))
            return ProviderReserveResult(success=True, provider_reservation_ref=provider_reservation_ref)
        except ProviderRequestError as e:
            return ProviderReserveResult(
                success=False, provider_reservation_ref=provider_reservation_ref, error_message=e.message
            )