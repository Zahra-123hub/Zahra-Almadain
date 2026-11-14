"""Results of the system check (database, migrations) with their time."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0032_system_checks"
down_revision: str | None = "0031_activity_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("checked_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("database_ok", sa.Boolean(), nullable=False),
        sa.Column("migrations_ok", sa.Boolean(), nullable=True),
        sa.Column("details", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_system_checks_checked_at", "system_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_system_checks_checked_at", table_name="system_checks")
    op.drop_table("system_checks")
