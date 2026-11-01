"""Anonymous visits of the public website (counted per day, no addresses kept)."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0023_site_visits"
down_revision: str | None = "0022_row_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_visits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("path", sa.String(length=80), nullable=False),
        sa.Column("referrer", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("device", sa.String(length=10), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False, server_default=""),
        sa.Column("visitor", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_site_visits_day", "site_visits", ["day"])
    op.create_index("ix_site_visits_visitor", "site_visits", ["visitor"])


def downgrade() -> None:
    op.drop_table("site_visits")
