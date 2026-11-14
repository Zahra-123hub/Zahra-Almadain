"""The day a child left the kindergarten."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0033_child_left_on"
down_revision: str | None = "0032_system_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("children", sa.Column("left_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("children", "left_on")
