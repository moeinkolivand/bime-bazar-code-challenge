from fastapi import Depends
from sqlalchemy import select
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

        Pessimistic locking: acquires a SELECT ... FOR UPDATE row lock via
        get_locked() first, then mutates the in-memory object. The row lock —
        not a WHERE-clause version check — is what guarantees no concurrent
        writer can interleave with this read-modify-write.
        Caller must guarantee idempotency (don't call twice for same reservation).
        Silently no-ops if the row no longer exists, matching the previous
        atomic-UPDATE behavior (0 rows affected).
        """
        inventory = self.get_locked(product_inventory_id)
        if inventory is None:
            return
        inventory.qty_available += quantity
        inventory.qty_reserved -= quantity
        inventory.version += 1

    def consume_hold(self, product_inventory_id: int, quantity: int) -> None:
        """
        Permanently consume reserved stock (confirmation).

        Pessimistic locking: acquires a SELECT ... FOR UPDATE row lock via
        get_locked() first, then mutates the in-memory object in place.
        Removes from reserved without restoring to available.
        Silently no-ops if the row no longer exists, matching the previous
        atomic-UPDATE behavior (0 rows affected).
        """
        inventory = self.get_locked(product_inventory_id)
        if inventory is None:
            return
        inventory.qty_reserved -= quantity
        inventory.version += 1


def get_inventory_repository(
    db: Session = Depends(get_db_postgres),
) -> InventoryRepository:
    return InventoryRepository(db)