from fastapi import Depends
from app.modules.inventory.providers.provider_registry import ProviderRegistry
from app.modules.inventory.services.provider_service import ProviderService


def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()


def get_provider_service(
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> ProviderService:
    return ProviderService(provider_registry=registry)
