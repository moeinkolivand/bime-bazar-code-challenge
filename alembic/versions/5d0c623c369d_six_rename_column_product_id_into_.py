"""six rename column product id into product_inventory_id

Revision ID: 5d0c623c369d
Revises: 38dd235392b0
Create Date: 2026-07-31 21:17:21.361353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d0c623c369d'
down_revision: Union[str, Sequence[str], None] = '38dd235392b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: rename product_id -> product_inventory_id."""
    # Step 1: Add the new column as nullable (so existing rows get NULL)
    op.add_column('reservation_items', sa.Column('product_inventory_id', sa.Integer(), nullable=True))
    
    # Step 2: Copy data from the old column to the new one
    op.execute("UPDATE reservation_items SET product_inventory_id = product_id")
    
    # Step 3: Make the new column NOT NULL (now that all rows have values)
    op.alter_column('reservation_items', 'product_inventory_id', nullable=False)
    
    # Step 4: Drop the old foreign key constraint (named by Alembic)
    op.drop_constraint(op.f('reservation_items_product_id_fkey'), 'reservation_items', type_='foreignkey')
    
    # Step 5: Drop the old column
    op.drop_column('reservation_items', 'product_id')
    
    # Step 6: Create the new foreign key constraint
    op.create_foreign_key(
        op.f('reservation_items_product_inventory_id_fkey'),  # use consistent naming
        'reservation_items',
        'product_inventories',
        ['product_inventory_id'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema: revert to product_id."""
    # Step 1: Add the old column as nullable
    op.add_column('reservation_items', sa.Column('product_id', sa.Integer(), nullable=True))
    
    # Step 2: Copy data from the new column back to the old one
    op.execute("UPDATE reservation_items SET product_id = product_inventory_id")
    
    # Step 3: Make old column NOT NULL
    op.alter_column('reservation_items', 'product_id', nullable=False)
    
    # Step 4: Drop the new foreign key constraint
    op.drop_constraint(op.f('reservation_items_product_inventory_id_fkey'), 'reservation_items', type_='foreignkey')
    
    # Step 5: Drop the new column
    op.drop_column('reservation_items', 'product_inventory_id')
    
    # Step 6: Re‑create the old foreign key constraint
    op.create_foreign_key(
        op.f('reservation_items_product_id_fkey'),
        'reservation_items',
        'product_inventories',
        ['product_id'],
        ['id']
    )