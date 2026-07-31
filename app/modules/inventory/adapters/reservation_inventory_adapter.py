from app.modules.inventory.repositories.inventory_repository import InventoryRepository
from app.modules.inventory.services.provider_service import ProviderService
from app.modules.reservation.dtoes.inventory_hold_result import InventoryHoldResult
from app.modules.reservation.public_api.public_inventory_api_interface import InventoryPublicApiInterface


class ReservationInventoryAdapter(InventoryPublicApiInterface):
    def __init__(self, inventory_repo: InventoryRepository, provider_service: ProviderService):
        self.inventory_repo = inventory_repo
        self.provider_service = provider_service

    def hold_stock(self, product_inventory_id: int, quantity: int) -> bool:
        inventory = self.inventory_repo.get_for_update_check(product_inventory_id)
        return self.inventory_repo.try_hold(product_inventory_id, quantity, inventory.version)

    def release_stock(self, product_inventory_id: int, quantity: int) -> None:
        self.inventory_repo.release_hold(product_inventory_id, quantity)

    def consume_stock(self, product_inventory_id: int, quantity: int) -> None:
        self.inventory_repo.consume_hold(product_inventory_id, quantity)

    def reserve_upstream(self, product_inventory_id, sku, quantity, idempotency_key) -> InventoryHoldResult:
        inventory = self.inventory_repo.get_for_update_check(product_inventory_id)
        outcome = self.provider_service.reserve(inventory.provider, sku, quantity, idempotency_key)
        return InventoryHoldResult(success=outcome.success, provider_reservation_ref=outcome.provider_reservation_ref)

    def confirm_upstream(self, product_inventory_id, provider_reservation_ref, idempotency_key) -> bool:
        inventory = self.inventory_repo.get_for_update_check(product_inventory_id)
        result = self.provider_service.confirm(inventory.provider, provider_reservation_ref, idempotency_key)
        return result.success

    def release_upstream(self, product_inventory_id, provider_reservation_ref) -> None:
        inventory = self.inventory_repo.get_for_update_check(product_inventory_id)
        self.provider_service.release(inventory.provider, provider_reservation_ref)

    def revalidate_stock(self, product_inventory_id, sku, required_quantity) -> bool:
        inventory = self.inventory_repo.get_for_update_check(product_inventory_id)
        return self.provider_service.revalidate_stock(inventory.provider, sku, required_quantity)