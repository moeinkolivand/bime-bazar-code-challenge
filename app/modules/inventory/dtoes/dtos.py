from dataclasses import dataclass, field


@dataclass
class RequestSpec:
    method: str
    path: str
    headers: dict | None = None
    params: dict | None = None
    json_body: dict | None = None


@dataclass
class ProviderResponse:
    status_code: int
    json_body: dict | None
    raw_text: str | None = None


@dataclass
class ProviderStockResult:
    success: bool
    qty_available: int | None = None
    error_message: str | None = None


@dataclass
class ProviderReserveResult:
    success: bool
    provider_reservation_ref: str | None = None
    error_message: str | None = None

@dataclass
class ReserveOutcome:
    success: bool
    provider_reservation_ref: str | None
    upstream_reserved: bool  # True only if an actual upstream hold was placed
    error_message: str | None = None


@dataclass
class ConfirmOutcome:
    success: bool
    error_message: str | None = None
