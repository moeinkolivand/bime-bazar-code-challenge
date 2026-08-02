"""ten add missing reservationitemstatus enum value HELD_LOCAL

Same class of drift as the reservationstatus fix: the reservationitemstatus
enum type was created with PENDING, HELD, FAILED, RELEASED, CONFIRMED. The
ReservationItemStatus model has since dropped PENDING and added HELD_LOCAL
(local stock reserved, upstream hold not yet attempted) — but no migration
ever added HELD_LOCAL to the Postgres enum type, so inserting a
reservation_items row with status=HELD_LOCAL fails with:
    psycopg.errors.InvalidTextRepresentation: invalid input value for
    enum reservationitemstatus: "HELD_LOCAL"

Note: the DB type still carries the old 'PENDING' label too. Postgres
cannot drop enum values, and nothing in the app writes 'PENDING' for this
column anymore, so it's left as harmless drift rather than requiring a
type-rewrite migration.

Revision ID: 2d99b0c3bf5f
Revises: 12f83a485f4f
Create Date: 2026-08-02 02:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2d99b0c3bf5f"
down_revision: Union[str, Sequence[str], None] = "12f83a485f4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE reservationitemstatus ADD VALUE IF NOT EXISTS 'HELD_LOCAL'"
        )


def downgrade() -> None:
    """Downgrade schema.

    Postgres does not support removing a value from an enum type directly.
    Left as a manual/no-op since this migration only adds capability.
    """
    pass
