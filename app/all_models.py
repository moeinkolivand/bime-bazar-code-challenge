"""
Import every SQLAlchemy model class here, for the side effect of registering
its table with the shared Base.metadata / mapper registry.

Why this file exists:
SQLAlchemy resolves string-based ForeignKey("some_table.id") targets against
whatever tables have actually been registered by the time mappers are
configured (lazily, on first ORM use, or explicitly via configure_mappers()).
A table is only registered once its model class has been imported *somewhere*
in the running process — merely existing on disk isn't enough.

Before this file existed, Product was only ever imported by app/seed.py.
Any other process — the main FastAPI app, or app/workers/expiry_worker.py —
that never happened to import app.modules.product.models.product would fail
the first time it touched a mapper that (transitively) referenced the
"products" table, with:
    sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column
    'product_inventories.product_id' could not find table 'products'

Import this module (or anything that imports it, like app.composition) once,
early, in every process entrypoint: the FastAPI app, the expiry worker,
seed.py, and alembic/env.py.
"""

from app.modules.product.models.product import Product  # noqa: F401
from app.modules.inventory.models.inventory_provider import (  # noqa: F401
    InventoryProvider,
)
from app.modules.inventory.models.inventory_product import (
    ProductInventory,
)  # noqa: F401
from app.modules.inventory.models.provider_call_log import ProviderCallLog  # noqa: F401
from app.modules.reservation.models.reservation import Reservation  # noqa: F401
from app.modules.reservation.models.reservation_item import (
    ReservationItem,
)  # noqa: F401
from app.modules.order.models.order import Order  # noqa: F401
from app.modules.order.models.order_item import OrderItem  # noqa: F401
from app.modules.user.models.user import User  # noqa: F401
from app.modules.user.models.otp import Otp  # noqa: F401

__all__ = [
    "Product",
    "InventoryProvider",
    "ProductInventory",
    "ProviderCallLog",
    "Reservation",
    "ReservationItem",
    "Order",
    "OrderItem",
    "User",
    "Otp",
]
