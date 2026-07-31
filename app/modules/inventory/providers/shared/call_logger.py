import time
from datetime import datetime
from typing import Callable, TypeVar
from app.modules.inventory.repositories.provider_call_log_repository import (
    ProviderCallLogRepository,
)
from app.modules.inventory.models.provider_call_log import (
    ProviderCallType,
    ProviderCallOutcome,
)
from app.modules.inventory.exceptions.provider_request_error import ProviderRequestError
from app.modules.inventory.providers.shared.circuit_breaker import CircuitOpenError

T = TypeVar("T")


class CallLogger:
    def __init__(self, log_repo: ProviderCallLogRepository, provider_id: int):
        self.log_repo = log_repo
        self.provider_id = provider_id

    def execute(
        self,
        fn: Callable[[], T],
        call_type: ProviderCallType,
        reservation_item_id: int | None = None,
        request_payload: dict | None = None,
    ) -> T:
        start = time.monotonic()
        attempted_at = datetime.now()
        try:
            result = fn()
            self.log_repo.log(
                provider_id=self.provider_id,
                reservation_item_id=reservation_item_id,
                call_type=call_type,
                outcome=ProviderCallOutcome.SUCCESS,
                request_payload=request_payload,
                response_payload=None,
                error_message=None,
                latency_ms=int((time.monotonic() - start) * 1000),
                attempted_at=attempted_at,
            )
            return result
        except (ProviderRequestError, CircuitOpenError) as e:
            outcome = (
                ProviderCallOutcome.TIMEOUT
                if isinstance(e, ProviderRequestError) and e.is_timeout
                else ProviderCallOutcome.FAILURE
            )
            self.log_repo.log(
                provider_id=self.provider_id,
                reservation_item_id=reservation_item_id,
                call_type=call_type,
                outcome=outcome,
                request_payload=request_payload,
                response_payload=None,
                error_message=str(e),
                latency_ms=int((time.monotonic() - start) * 1000),
                attempted_at=attempted_at,
            )
            raise
