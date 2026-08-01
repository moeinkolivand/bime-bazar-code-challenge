from pydantic import BaseModel, field_validator


class ReservationItemRequest(BaseModel):
    product_inventory_id: int
    sku: str
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v


class CreateReservationDto(BaseModel):
    items: list[ReservationItemRequest]
    client_idempotency_key: str
