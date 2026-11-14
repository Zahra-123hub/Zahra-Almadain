"""Explicit permissions for single accounts (for example the control centre)."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0034_account_grants"
down_revision: str | None = "0033_child_left_on"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grant_name", sa.String(length=40), nullable=False),
        sa.Column("granted_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("granted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("account_id", "grant_name", name="uq_account_grant"),
    )
    op.create_index("ix_account_grants_account_id", "account_grants", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_account_grants_account_id", table_name="account_grants")
    op.drop_table("account_grants")
