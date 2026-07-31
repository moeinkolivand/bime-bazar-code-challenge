from fastapi import Depends

from app.modules.inventory.dependecies import get_provider_service
from app.modules.inventory.repositories.inventory_repository import InventoryRepository, get_inventory_repository
from app.modules.inventory.services.provider_service import ProviderService
from app.modules.inventory.adapters.reservation_inventory_adapter import ReservationInventoryAdapter
from app.modules.reservation.public_api.public_inventory_api_interface import InventoryPublicApiInterface
from app.modules.reservation.repositories.reservation_repository import ReservationRepository, get_reservation_repository
from app.modules.reservation.services.reservation_items_service import ReservationItemReserver
from app.modules.reservation.services.reservation_service import ReservationService
from app.core.conf.config import Settings, get_settings


def get_inventory_port(
    inventory_repo: InventoryRepository = Depends(get_inventory_repository),
    provider_service: ProviderService = Depends(get_provider_service),
) -> InventoryPublicApiInterface:
    return ReservationInventoryAdapter(inventory_repo, provider_service)


def get_reservation_item_reserver(
    reservation_repo: ReservationRepository = Depends(get_reservation_repository),
    inventory_port: InventoryPublicApiInterface = Depends(get_inventory_port),
) -> ReservationItemReserver:
    return ReservationItemReserver(reservation_repo, inventory_port)


def get_reservation_service(
    reservation_repo: ReservationRepository = Depends(get_reservation_repository),
    inventory_port: InventoryPublicApiInterface = Depends(get_inventory_port),
    item_reserver: ReservationItemReserver = Depends(get_reservation_item_reserver),
    config: Settings = Depends(get_settings),
) -> ReservationService:
    return ReservationService(reservation_repo, inventory_port, item_reserver, config.RESERVATION_TTL_SECONDS)