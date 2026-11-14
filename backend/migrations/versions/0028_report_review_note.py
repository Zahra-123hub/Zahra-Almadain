"""The management can give a reason when it returns a report to the teacher."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0028_report_review_note"
down_revision: str | None = "0027_material_course"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_reports", sa.Column("review_note", sa.String(length=500), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("daily_reports", "review_note")
