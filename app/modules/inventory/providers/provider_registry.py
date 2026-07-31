from app.modules.inventory.exceptions.provider_not_found import UnknownProviderKeyError, ProviderMisconfiguredError
from app.modules.inventory.models.inventory_provider import InventoryProvider
from app.modules.inventory.providers.interfaces.capabilities import Reservable
from app.modules.inventory.providers.provider_implementation.internal_provider.internal_provider import InternalProviderClient
from app.modules.inventory.providers.provider_implementation.markertplace.market_place_provider import MarketplaceSellerXProviderClient
from app.modules.inventory.providers.provider_implementation.warehouse_provider.warehouse_provider import WarehouseProviderClient


class ProviderRegistry:
    def __init__(self):
        self._provider_classes: dict[str, type] = {
            "internal": InternalProviderClient,
            "warehouse_provider": WarehouseProviderClient,
            "marketplace_seller_x": MarketplaceSellerXProviderClient,
        }
        self._instances: dict[str, object] = {}

    def get_client(self, provider: InventoryProvider):
        key = provider.name
        if key not in self._provider_classes:
            raise UnknownProviderKeyError(key)

        if key not in self._instances:
            self._instances[key] = self._provider_classes[key](provider=provider)
            self._assert_capability_consistency(provider, self._instances[key])

        return self._instances[key]

    def _assert_capability_consistency(self, provider: InventoryProvider, client) -> None:
        can_reserve_flag = provider.capabilities.get("can_reserve", False)
        implements_reservable = isinstance(client, Reservable)
        if can_reserve_flag != implements_reservable:
            raise ProviderMisconfiguredError(
                provider.name,
                f"capabilities.can_reserve={can_reserve_flag} but client "
                f"{'implements' if implements_reservable else 'does not implement'} Reservable",
            )
