"""A version, the time and the name of the last change on fee lines, salary lines and sheet rows."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0022_row_versions"
down_revision: str | None = "0021_entry_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("fee_charges", "salary_lines", "accounting_entries")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        op.add_column(table, sa.Column("updated_at", sa.DateTime(), nullable=True))
        op.add_column(table, sa.Column("updated_by", sa.String(length=80), nullable=False, server_default=""))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "updated_by")
        op.drop_column(table, "updated_at")
        op.drop_column(table, "version")
