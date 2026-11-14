"""A session knows its active role, when it was last used and from what kind of device (hashes only)."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0030_session_meta"
down_revision: str | None = "0029_cash_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("portal_sessions", sa.Column("active_role", sa.String(length=20), nullable=True))
    op.add_column("portal_sessions", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column("portal_sessions", sa.Column("ip_hash", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("portal_sessions", sa.Column("user_agent_hash", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("portal_sessions", sa.Column("device_label", sa.String(length=80), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("portal_sessions", "device_label")
    op.drop_column("portal_sessions", "user_agent_hash")
    op.drop_column("portal_sessions", "ip_hash")
    op.drop_column("portal_sessions", "last_seen_at")
    op.drop_column("portal_sessions", "active_role")
