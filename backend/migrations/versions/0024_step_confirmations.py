"""A step of the accounting workflow can be confirmed as complete on purpose, per month."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0024_step_confirmations"
down_revision: str | None = "0023_site_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "step_confirmations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(length=20), nullable=False),
        sa.Column("confirmed_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("confirmed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("year", "month", "step", name="uq_step_confirmation"),
    )
    op.create_index("ix_step_confirmations_year", "step_confirmations", ["year"])


def downgrade() -> None:
    op.drop_table("step_confirmations")
