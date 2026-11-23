"""Everyday life of a child: notes (praise / remark), things to bring, the week plan of a group, attendance, messages with the parents.
New tables only."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0042_child_everyday"
down_revision: str | None = "0041_money_test_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "child_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="note"),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_child_notes_child_id", "child_notes", ["child_id"])
    op.create_index("ix_child_notes_created_at", "child_notes", ["created_at"])

    op.create_table(
        "bring_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("class_name", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bring_items_class_name", "bring_items", ["class_name"])
    op.create_index("ix_bring_items_child_id", "bring_items", ["child_id"])
    op.create_index("ix_bring_items_created_at", "bring_items", ["created_at"])

    op.create_table(
        "week_plan_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("class_name", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("detail", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_week_plan_entries_class_name", "week_plan_entries", ["class_name"])

    op.create_table(
        "attendance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("by_parent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("set_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("set_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("child_id", "day", name="uq_attendance_child_day"),
    )
    op.create_index("ix_attendance_child_id", "attendance", ["child_id"])
    op.create_index("ix_attendance_day", "attendance", ["day"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("from_parent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_child_id", "chat_messages", ["child_id"])
    op.create_index("ix_chat_messages_parent_id", "chat_messages", ["parent_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    for table in ("chat_messages", "attendance", "week_plan_entries", "bring_items", "child_notes"):
        op.drop_table(table)
