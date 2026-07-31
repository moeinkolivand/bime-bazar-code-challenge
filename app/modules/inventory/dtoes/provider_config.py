# modules/inventory/providers/config.py
from dataclasses import dataclass

from app.modules.inventory.models.inventory_provider import InventoryProvider


@dataclass
class ProviderConfig:
    base_url: str
    protocol: str  # "rest" | "soap" | "grpc"
    timeout_seconds: float
    max_retries: int
    base_retry_delay_seconds: float
    circuit_breaker_failure_threshold: int
    circuit_breaker_cooldown_seconds: float

    @classmethod
    def from_provider_model(cls, provider: "InventoryProvider") -> "ProviderConfig":
        """provider.capabilities (JSON) is the config source of truth — read from DB, not hardcoded."""
        cfg = provider.capabilities or {}
        return cls(
            base_url=cfg["base_url"],
            protocol=cfg.get("protocol", "rest"),
            timeout_seconds=cfg.get("timeout_seconds", 3.0),
            max_retries=cfg.get("max_retries", 3),
            base_retry_delay_seconds=cfg.get("base_retry_delay_seconds", 0.5),
            circuit_breaker_failure_threshold=cfg.get("circuit_breaker_failure_threshold", 5),
            circuit_breaker_cooldown_seconds=cfg.get("circuit_breaker_cooldown_seconds", 30.0),
        )