"""nine add missing reservationstatus enum values

The reservationstatus enum type was created with only PENDING, CONFIRMED,
CANCELLED, EXPIRED. The ReservationStatus model was later extended with
CREATING, PENDING_LOCAL, and CONFIRMING to support the multi-step
create/confirm flow (local hold -> upstream hold -> pending, and a
confirming lock state), but no migration ever added those labels to the
Postgres enum type itself. Any INSERT/UPDATE/SELECT using one of those
three statuses currently fails with:
    psycopg.errors.InvalidTextRepresentation: invalid input value for
    enum reservationstatus: "PENDING_LOCAL"

Revision ID: 12f83a485f4f
Revises: 89cce1029dc7
Create Date: 2026-08-02 01:40:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12f83a485f4f"
down_revision: Union[str, Sequence[str], None] = "89cce1029dc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction that
    # also uses the new value, but can run inside a transaction on its own
    # (Postgres 12+). autocommit_block() runs each statement outside of
    # alembic's normal transaction wrapping.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE reservationstatus ADD VALUE IF NOT EXISTS 'CREATING'")
        op.execute(
            "ALTER TYPE reservationstatus ADD VALUE IF NOT EXISTS 'PENDING_LOCAL'"
        )
        op.execute("ALTER TYPE reservationstatus ADD VALUE IF NOT EXISTS 'CONFIRMING'")


def downgrade() -> None:
    """Downgrade schema.

    Postgres does not support removing a value from an enum type directly.
    Downgrading would require creating a new enum type without the three
    values, rewriting the column to it, and dropping the old type — and
    would fail outright if any row currently holds CREATING, PENDING_LOCAL,
    or CONFIRMING. Left as a manual/no-op since this migration only adds
    capability and never removes existing data.
    """
    pass
