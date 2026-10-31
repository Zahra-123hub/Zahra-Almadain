"""Closed accounting months and cash reconciliations."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0018_period_locks_cash_counts"
down_revision: str | None = "0017_exchange_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "period_locks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("closed_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("closed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("snapshot", sa.String(length=1000), nullable=False, server_default=""),
        sa.UniqueConstraint("year", "month", name="uq_period_lock"),
    )
    op.create_index("ix_period_locks_year", "period_locks", ["year"])
    op.create_table(
        "cash_counts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("counted_on", sa.Date(), nullable=False),
        sa.Column("counted_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("book_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("difference", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("counted_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cash_counts_currency", "cash_counts", ["currency"])
    op.create_index("ix_cash_counts_counted_on", "cash_counts", ["counted_on"])


def downgrade() -> None:
    op.drop_index("ix_cash_counts_counted_on", table_name="cash_counts")
    op.drop_index("ix_cash_counts_currency", table_name="cash_counts")
    op.drop_table("cash_counts")
    op.drop_index("ix_period_locks_year", table_name="period_locks")
    op.drop_table("period_locks")
