"""Phones that signed in to the mobile app (for push messages)."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0025_device_tokens"
down_revision: str | None = "0024_step_confirmations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=300), nullable=False, unique=True),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("app_version", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("language", sa.String(length=5), nullable=False, server_default="ar"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_device_tokens_account_id", "device_tokens", ["account_id"])


def downgrade() -> None:
    op.drop_table("device_tokens")
