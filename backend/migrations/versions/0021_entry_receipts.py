"""Receipts (files and numbers) for the rows of the accounting sheets."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0021_entry_receipts"
down_revision: str | None = "0020_community"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounting_entries", sa.Column("receipt_no", sa.String(length=60), nullable=False, server_default=""))
    op.create_table(
        "entry_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(), sa.ForeignKey("accounting_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(length=180), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("contents", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_entry_receipts_entry_id", "entry_receipts", ["entry_id"])


def downgrade() -> None:
    op.drop_table("entry_receipts")
    op.drop_column("accounting_entries", "receipt_no")
