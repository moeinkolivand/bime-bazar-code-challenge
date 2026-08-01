from dataclasses import dataclass


@dataclass
class InventoryHoldResult:
    success: bool
    provider_reservation_ref: str | None = None
    upstream_reserved: bool = False
