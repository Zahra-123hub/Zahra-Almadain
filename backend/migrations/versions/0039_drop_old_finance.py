"""Removes the tables of the old accounting.

Safety: tables that still hold rows are only dropped when a backup made with `python -m app.manage finance-backup` is named in the
variable OLD_FINANCE_BACKUP_DIR and that backup is checked here against the database (every file there, unchanged, same row
counts). Without it the old tables are left exactly as they are and this migration only removes what is empty; run
`python -m app.manage drop-old-finance --backup <folder>` later to remove them after a checked backup.

The two rights of migration 0037 (books.view, books.write) go too: the accountant now always sees and records; changing,
cancelling and exporting have their own rights (books.correct, books.export).

There is no way back by downgrade: the old tables can only be restored from the backup.
"""

import os
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0039_drop_old_finance"
down_revision: str | None = "0038_money"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM account_grants WHERE grant_name IN ('books.view', 'books.write')"))
    from app.finance_backup import drop_old_tables

    result = drop_old_tables(bind, os.getenv("OLD_FINANCE_BACKUP_DIR"))
    if result["kept"]:
        print("0039: the old accounting tables were KEPT (they hold rows and no checked backup was named): " + ", ".join(result["kept"]))


def downgrade() -> None:
    raise RuntimeError("The old accounting tables cannot be rebuilt by a downgrade. Restore them from the finance backup.")
