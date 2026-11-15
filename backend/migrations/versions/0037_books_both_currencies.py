"""The three accounting pages (income, expenses, month overview): every booking keeps the rate it was made with and the value in the
other currency; a booking may point to a person of the staff or to a child. Existing accountant accounts keep their access by explicit
grants (books.view, books.write). Additive: no booking is changed."""

import uuid
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0037_books_both"
down_revision: str | None = "0036_invoices_both"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cash_transactions", sa.Column("amount_other", sa.Numeric(14, 2), nullable=True))
    op.add_column("cash_transactions", sa.Column("rate_syp_per_usd", sa.Numeric(18, 6), nullable=True))
    op.add_column("cash_transactions", sa.Column("rate_date", sa.Date(), nullable=True))
    op.add_column("cash_transactions", sa.Column("rate_source", sa.String(length=14), nullable=False, server_default="none"))
    op.add_column("cash_transactions", sa.Column("note", sa.String(length=500), nullable=False, server_default=""))
    with op.batch_alter_table("cash_transactions") as batch:  # batch mode: SQLite cannot add a foreign key by ALTER
        batch.add_column(sa.Column("employee_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("child_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_cash_tx_employee", "employees", ["employee_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_cash_tx_child", "children", ["child_id"], ["id"], ondelete="SET NULL")
    # the accountants that exist today keep working: they get the two rights once (the administrator can take them away again)
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT a.id FROM accounts a JOIN account_roles ar ON ar.account_id = a.id JOIN roles r ON r.id = ar.role_id WHERE r.name = 'accountant'"
    )).fetchall()
    for (account_id,) in rows:
        for grant in ("books.view", "books.write"):
            bind.execute(
                sa.text("INSERT INTO account_grants (id, account_id, grant_name, granted_by) VALUES (:id, :a, :g, :by)"),
                {"id": uuid.uuid4().hex if bind.dialect.name == "sqlite" else uuid.uuid4(), "a": account_id, "g": grant, "by": "migration 0037"},
            )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM account_grants WHERE grant_name IN ('books.view', 'books.write') AND granted_by = 'migration 0037'"))
    with op.batch_alter_table("cash_transactions") as batch:
        batch.drop_constraint("fk_cash_tx_child", type_="foreignkey")
        batch.drop_constraint("fk_cash_tx_employee", type_="foreignkey")
        for column in ("child_id", "employee_id", "note", "rate_source", "rate_date", "rate_syp_per_usd", "amount_other"):
            batch.drop_column(column)
