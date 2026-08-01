from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import get_db_postgres
from app.modules.inventory.models.inventory_product import ProductInventory

__all__ = ["InventoryRepository", "get_inventory_repository"]


class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_locked(self, product_inventory_id: int) -> ProductInventory | None:
        """
        Acquire an exclusive row-level lock (SELECT ... FOR UPDATE).

        Blocks other transactions from locking the same row until
        this transaction commits or rolls back.

        Must be called within an active transaction.
        Returns None if the row does not exist.
        """
        stmt = (
            select(ProductInventory)
            .where(ProductInventory.id == product_inventory_id)
            .with_for_update()
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def hold_locked(self, inventory: ProductInventory, quantity: int) -> bool:
        """
        Move quantity from available to reserved.

        Call ONLY after get_locked() on the same row in the same transaction.
        The row lock guarantees no concurrent modification.

        Returns False if insufficient stock.
        """
        if inventory.qty_available < quantity:
            return False

        inventory.qty_available -= quantity
        inventory.qty_reserved += quantity
        inventory.version += 1

        return True

    def release_hold(self, product_inventory_id: int, quantity: int) -> None:
        """
        Return reserved quantity back to available.

        Atomic UPDATE — safe under concurrency.
        Caller must guarantee idempotency (don't call twice for same reservation).
        """
        stmt = (
            update(ProductInventory)
            .where(ProductInventory.id == product_inventory_id)
            .values(
                qty_available=ProductInventory.qty_available + quantity,
                qty_reserved=ProductInventory.qty_reserved - quantity,
                version=ProductInventory.version + 1,
            )
        )
        self.db.execute(stmt)

    def consume_hold(self, product_inventory_id: int, quantity: int) -> None:
        """
        Permanently consume reserved stock (confirmation).

        Removes from reserved without restoring to available.
        Atomic UPDATE — safe under concurrency.
        """
        stmt = (
            update(ProductInventory)
            .where(ProductInventory.id == product_inventory_id)
            .values(
                qty_reserved=ProductInventory.qty_reserved - quantity,
                version=ProductInventory.version + 1,
            )
        )
        self.db.execute(stmt)


def get_inventory_repository(
    db: Session = Depends(get_db_postgres),
) -> InventoryRepository:
    return InventoryRepository(db)
