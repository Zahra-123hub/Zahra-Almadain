"""Birth date of a child and the father / mother (guardians) of every child."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0019_child_guardians"
down_revision: str | None = "0018_period_locks_cash_counts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("children", sa.Column("birth_date", sa.Date(), nullable=True))
    op.create_table(
        "child_guardians",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=254), nullable=False, server_default=""),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("child_id", "relation", name="uq_child_guardian_relation"),
    )
    op.create_index("ix_child_guardians_child_id", "child_guardians", ["child_id"])


def downgrade() -> None:
    op.drop_index("ix_child_guardians_child_id", table_name="child_guardians")
    op.drop_table("child_guardians")
    op.drop_column("children", "birth_date")
