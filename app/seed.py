"""
Seed script — populates Products, InventoryProviders, and ProductInventory rows
for local testing / demoing the reservation flow.

Run with:
    python -m app.seed
(adjust the import path below to match wherever your SessionLocal/engine live)
"""

from app.core.database.postgres.postgres import SessionLocal
from app.modules.inventory.models.inventory_product import ProductInventory
from app.modules.inventory.models.inventory_provider import InventoryProvider, ProviderType
from app.modules.product.models.product import Product

def seed():
    db = SessionLocal()
    try:
        internal_provider = InventoryProvider(
            name="internal",
            provider_type=ProviderType.INTERNAL,
            capabilities={"can_check_stock": True, "can_reserve": True},
            credentials_ref=None,
            is_active=True,
        )

        warehouse_provider = InventoryProvider(
            name="warehouse_provider",
            provider_type=ProviderType.EXTERNAL,
            capabilities={"can_check_stock": True, "can_reserve": True},
            credentials_ref="warehouse-provider-api-key-ref",
            is_active=True,
        )

        marketplace_seller_x = InventoryProvider(
            name="marketplace_seller_x",
            provider_type=ProviderType.EXTERNAL,
            capabilities={"can_check_stock": True, "can_reserve": False},
            credentials_ref="marketplace-seller-x-ref",
            is_active=True,
        )

        db.add_all([internal_provider, warehouse_provider, marketplace_seller_x])
        db.flush() 

        sony_headphones = Product(
            name="Sony WH-1000XM5 Headphones",
            sku="SONY-WH-XM5-BLK",
        )

        anker_hub = Product(
            name="Anker USB-C Hub 7-in-1",
            sku="ANKR-HUB-7C",
        )

        logitech_mouse = Product(
            name="Logitech MX Master 3S",
            sku="LOGI-MXM3S-GRY",
        )

        db.add_all([sony_headphones, anker_hub, logitech_mouse])
        db.flush()

        inventories = [
            ProductInventory(
                product_id=sony_headphones.id,
                provider_id=warehouse_provider.id,
                qty_available=12,
                qty_reserved=0,
                version=0,
            ),
            ProductInventory(
                product_id=sony_headphones.id,
                provider_id=marketplace_seller_x.id,
                qty_available=5,
                qty_reserved=0,
                version=0,
            ),
            ProductInventory(
                product_id=anker_hub.id,
                provider_id=internal_provider.id,
                qty_available=340,
                qty_reserved=0,
                version=0,
            ),
            ProductInventory(
                product_id=logitech_mouse.id,
                provider_id=internal_provider.id,
                qty_available=2,
                qty_reserved=0,
                version=0,
            ),
        ]

        db.add_all(inventories)
        db.commit()

        print("Seed complete:")
        print(f"  Providers: internal={internal_provider.id}, warehouse={warehouse_provider.id}, "
              f"marketplace_x={marketplace_seller_x.id}")
        print(f"  Products: sony={sony_headphones.id}, anker={anker_hub.id}, logitech={logitech_mouse.id}")
        for inv in inventories:
            print(f"  ProductInventory: id={inv.id} product_id={inv.product_id} "
                  f"provider_id={inv.provider_id} qty_available={inv.qty_available}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()