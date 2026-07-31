# modules/inventory/providers/capabilities.py
from abc import ABC, abstractmethod

from app.modules.inventory.dtoes.dtos import ProviderStockResult, ProviderReserveResult


class StockCheckable(ABC):
    @abstractmethod
    def check_stock(self, sku: str) -> ProviderStockResult: ...


class Reservable(ABC):
    @abstractmethod
    def reserve(
        self, sku: str, quantity: int, idempotency_key: str
    ) -> ProviderReserveResult: ...

    @abstractmethod
    def confirm(
        self, provider_reservation_ref: str, idempotency_key: str
    ) -> ProviderReserveResult: ...

    @abstractmethod
    def release(self, provider_reservation_ref: str) -> ProviderReserveResult: ...
