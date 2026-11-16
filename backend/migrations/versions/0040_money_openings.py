"""The money the kindergarten has (opening balance per currency, from a day on). New table only."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0040_money_openings"
down_revision: str | None = "0039_drop_old_finance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "money_openings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_money_openings_currency", "money_openings", ["currency"])


def downgrade() -> None:
    op.drop_index("ix_money_openings_currency", table_name="money_openings")
    op.drop_table("money_openings")
