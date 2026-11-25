"""Chats between one teacher and one parent (about one child), the management sees all of them.

Each message now knows the kindergarten side of its conversation (staff_id: the teacher; empty: the management) and the role
of whoever wrote it. Earlier messages: a teacher's own messages belong to her conversation, a parent's message to the
conversation of the first teacher who answered there; the rest stays with the management."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0043_chat_with_teachers"
down_revision: str | None = "0042_child_everyday"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("staff_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("chat_messages", sa.Column("sender_role", sa.String(length=12), nullable=False, server_default=""))
    op.create_index("ix_chat_messages_staff_id", "chat_messages", ["staff_id"])
    # who wrote the earlier messages, and which teacher's conversation they belong to
    op.execute("UPDATE chat_messages SET sender_role = 'parent' WHERE from_parent = true")
    op.execute("""
        UPDATE chat_messages SET staff_id = sender_id, sender_role = 'teacher'
        WHERE from_parent = false AND sender_id IN (
            SELECT ar.account_id FROM account_roles ar JOIN roles r ON r.id = ar.role_id WHERE r.name = 'teacher')
    """)
    op.execute("UPDATE chat_messages SET sender_role = 'manager' WHERE from_parent = false AND staff_id IS NULL")
    op.execute("""
        UPDATE chat_messages AS m SET staff_id = (
            SELECT t.staff_id FROM chat_messages t
            WHERE t.child_id = m.child_id AND t.parent_id = m.parent_id AND t.staff_id IS NOT NULL
            ORDER BY t.created_at LIMIT 1)
        WHERE m.from_parent = true
    """)


def downgrade() -> None:
    op.drop_index("ix_chat_messages_staff_id", table_name="chat_messages")
    op.drop_column("chat_messages", "sender_role")
    op.drop_column("chat_messages", "staff_id")
