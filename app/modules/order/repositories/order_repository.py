from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db_postgres
from app.modules.order.models.order import Order, OrderStatus
from app.modules.order.models.order_item import OrderItem

__all__ = ["OrderRepository", "get_order_repository"]


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, reservation_id: int) -> Order:
        order = Order(user_id=user_id, reservation_id=reservation_id, status=OrderStatus.CREATED)
        self.db.add(order)
        self.db.flush()
        return order

    def add_item(self, order_id: int, product_inventory_id: int, sku: str, quantity: int) -> OrderItem:
        item = OrderItem(
            order_id=order_id, product_inventory_id=product_inventory_id, sku=sku, quantity=quantity
        )
        self.db.add(item)
        self.db.flush()
        return item

    def get_by_id(self, order_id: int) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_reservation_id(self, reservation_id: int) -> Order | None:
        stmt = select(Order).where(Order.reservation_id == reservation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def flush(self) -> None:
        self.db.flush()


def get_order_repository(db: Session = Depends(get_db_postgres)) -> OrderRepository:
    return OrderRepository(db)