from pydantic import BaseModel


class ReservationItemRequest(BaseModel):
    product_inventory_id: int
    sku: str
    quantity: int


class CreateReservationDto(BaseModel):
    items: list[ReservationItemRequest]
