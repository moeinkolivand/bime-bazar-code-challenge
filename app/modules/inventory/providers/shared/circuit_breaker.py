import time
import enum
from typing import Callable, TypeVar
from app.modules.inventory.exceptions.provider_request_error import ProviderRequestError

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    """Generic — same state machine for every provider, only threshold/cooldown differ."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    def execute(self, fn: Callable[[], T]) -> T:
        if self._state == CircuitState.OPEN:
            if time.time() - self._opened_at >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("provider circuit is open")
        try:
            result = fn()
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            return result
        except ProviderRequestError:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
            raise ProviderRequestError
