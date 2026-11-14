"""The activity log covers every area, not only the money: each line says which area it belongs to."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0031_activity_domain"
down_revision: str | None = "0030_session_meta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fee_audit_log", sa.Column("domain", sa.String(length=20), nullable=False, server_default="finance"))
    op.create_index("ix_fee_audit_log_domain", "fee_audit_log", ["domain"])


def downgrade() -> None:
    op.drop_index("ix_fee_audit_log_domain", table_name="fee_audit_log")
    op.drop_column("fee_audit_log", "domain")
