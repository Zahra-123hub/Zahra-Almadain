"""Smooth links between parents and children: an invitation can be made for the father / mother of a child's record, and a
registration request remembers whether its approval made a new child (only such a child is renamed or removed with it)."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0044_family_links"
down_revision: str | None = "0043_chat_with_teachers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("guardian_invitations", sa.Column("relation", sa.String(length=10), nullable=False, server_default=""))
    op.add_column("registration_requests", sa.Column("created_child", sa.Boolean(), nullable=False, server_default=sa.false()))
    # every approval so far made its own child
    op.execute("UPDATE registration_requests SET created_child = true WHERE invitation_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("registration_requests", "created_child")
    op.drop_column("guardian_invitations", "relation")
