"""Posts can be learning material for parents (kind "material")."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0026_post_kind"
down_revision: str | None = "0025_device_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teacher_posts", sa.Column("kind", sa.String(length=10), nullable=False, server_default="post"))


def downgrade() -> None:
    op.drop_column("teacher_posts", "kind")
