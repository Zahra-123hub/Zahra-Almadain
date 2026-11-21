"""Test entries of the accounting: a flag on invoices, income and expenses so that trial data can be removed again."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0041_money_test_entries"
down_revision: str | None = "0040_money_openings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("invoices", "income_entries", "expense_entries")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "is_test")
