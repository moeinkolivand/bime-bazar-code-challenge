from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ConfirmedReservationItem:
    product_inventory_id: int
    sku: str
    quantity: int


@dataclass
class ConfirmedReservation:
    reservation_id: int
    user_id: int
    items: list[ConfirmedReservationItem]


class ReservationPort(ABC):
    @abstractmethod
    def get_confirmed_reservation(self, reservation_id: int) -> ConfirmedReservation | None:
        """Returns None if the reservation doesn't exist or isn't CONFIRMED."""
        pass
