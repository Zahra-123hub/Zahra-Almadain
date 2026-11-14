"""Learning material can be hidden and ordered, like the sections of a course."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0027_material_course"
down_revision: str | None = "0026_post_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teacher_posts", sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("teacher_posts", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("teacher_posts", "position")
    op.drop_column("teacher_posts", "hidden")
