"""Notifications, management announcements, activities and meals of a daily report."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0020_community"
down_revision: str | None = "0019_child_guardians"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_reports", sa.Column("activities", sa.String(length=1000), nullable=False, server_default=""))
    op.add_column("daily_reports", sa.Column("meals", sa.String(length=500), nullable=False, server_default=""))
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("view", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_account_id", "notifications", ["account_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_announcements_created_at", "announcements", ["created_at"])


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_table("notifications")
    op.drop_column("daily_reports", "meals")
    op.drop_column("daily_reports", "activities")
