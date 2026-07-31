from abc import ABC, abstractmethod
from app.modules.reservation.dtoes.inventory_hold_result import InventoryHoldResult



class InventoryPublicApiInterface(ABC):
    @abstractmethod
    def hold_stock(self, product_inventory_id: int, quantity: int) -> bool: ...

    @abstractmethod
    def release_stock(self, product_inventory_id: int, quantity: int) -> None: ...

    @abstractmethod
    def consume_stock(self, product_inventory_id: int, quantity: int) -> None: ...

    @abstractmethod
    def reserve_upstream(
        self, product_inventory_id: int, sku: str, quantity: int, idempotency_key: str
    ) -> InventoryHoldResult: ...

    @abstractmethod
    def confirm_upstream(
        self, product_inventory_id: int, provider_reservation_ref: str | None, idempotency_key: str
    ) -> bool: ...

    @abstractmethod
    def release_upstream(self, product_inventory_id: int, provider_reservation_ref: str | None) -> None: ...

    @abstractmethod
    def revalidate_stock(self, product_inventory_id: int, sku: str, required_quantity: int) -> bool: ...