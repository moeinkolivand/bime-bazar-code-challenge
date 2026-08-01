# modules/inventory/providers/retry.py
import time
from typing import Callable, TypeVar
from app.modules.inventory.exceptions.provider_request_error import ProviderRequestError

T = TypeVar("T")


class RetryPolicy:
    """Generic — same algorithm for every provider, only parameters differ."""

    def __init__(self, max_retries: int = 3, base_delay_seconds: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay_seconds

    def execute(self, fn: Callable[[], T]) -> T:
        last_error: ProviderRequestError | None = None
        for attempt in range(self.max_retries):
            try:
                return fn()
            except ProviderRequestError as e:
                last_error = e
                if not e.is_timeout:
                    raise
                time.sleep(self.base_delay * (2**attempt))
        raise last_error
