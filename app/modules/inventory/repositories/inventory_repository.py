from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import get_db_postgres
from app.modules.inventory.models.inventory_product import ProductInventory

__all__ = ["InventoryRepository", "get_inventory_repository"]


class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_update_check(self, product_inventory_id: int) -> ProductInventory | None:
        """Plain read — used to fetch the row's current version before an optimistic hold."""
        stmt = select(ProductInventory).where(ProductInventory.id == product_inventory_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_locked(self, product_inventory_id: int) -> ProductInventory | None:
        """
        Pessimistic row lock (SELECT ... FOR UPDATE). Used for internal-provider
        stock, where contention is expected to be highest and we own the row
        exclusively — blocks concurrent transactions until this one commits.
        """
        stmt = (
            select(ProductInventory)
            .where(ProductInventory.id == product_inventory_id)
            .with_for_update()
        )
        return self.db.execute(stmt).scalar_one_or_none()


    def hold_locked(self, inventory: ProductInventory, quantity: int) -> bool:
        """Call only after get_locked() — row is already locked, so a plain check+mutate is safe."""
        if inventory.qty_available < quantity:
            return False
        inventory.qty_available -= quantity
        inventory.qty_reserved += quantity
        inventory.version += 1
        return True


    def try_hold(self, product_inventory_id: int, quantity: int, expected_version: int) -> bool:
        """
        Atomically move stock available -> reserved, guarded by version.
        Returns False if another writer changed the row first (no rows matched).
        """
        stmt = (
            update(ProductInventory)
            .where(
                ProductInventory.id == product_inventory_id,
                ProductInventory.version == expected_version,
                ProductInventory.qty_available >= quantity,
            )
            .values(
                qty_available=ProductInventory.qty_available - quantity,
                qty_reserved=ProductInventory.qty_reserved + quantity,
                version=ProductInventory.version + 1,
            )
        )
        result = self.db.execute(stmt)
        return result.rowcount == 1


    def release_hold(self, product_inventory_id: int, quantity: int) -> None:
        """Undo a hold — reservation failed, expired, or was cancelled."""
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
        """Confirm: permanently remove from reserved (does not restore qty_available)."""
        stmt = (
            update(ProductInventory)
            .where(ProductInventory.id == product_inventory_id)
            .values(
                qty_reserved=ProductInventory.qty_reserved - quantity,
                version=ProductInventory.version + 1,
            )
        )
        self.db.execute(stmt)


def get_inventory_repository(db: Session = Depends(get_db_postgres)) -> InventoryRepository:
    return InventoryRepository(db)