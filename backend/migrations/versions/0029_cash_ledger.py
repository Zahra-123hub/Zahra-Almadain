"""The cash book: bookings, cancellations instead of deletions, receipts kept, a richer audit log, the cutover switch."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0029_cash_ledger"
down_revision: str | None = "0028_report_review_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _void_columns() -> list[sa.Column]:
    return [
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("void_reason", sa.String(length=300), nullable=False, server_default=""),
    ]


def upgrade() -> None:
    op.create_table(
        "cash_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("kind", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("booked_on", sa.Date(), nullable=False),
        sa.Column("date_basis", sa.String(length=24), nullable=False, server_default="actual"),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("counterparty", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("receipt_no", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("adjustment_kind", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("counts_in_cash", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("legacy_entry_id", sa.Uuid(), sa.ForeignKey("accounting_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("legacy_note", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("adjusts_salary_line_id", sa.Uuid(), sa.ForeignKey("salary_lines.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("adjusts_period", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("reverses_adjustment_id", sa.Uuid(), sa.ForeignKey("cash_transactions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by_id", sa.Uuid(), nullable=True),
        sa.Column("voided_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("void_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.UniqueConstraint("legacy_entry_id", "kind", name="uq_cash_tx_legacy_entry"),
    )
    op.create_index("ix_cash_transactions_booked_on", "cash_transactions", ["booked_on"])
    op.create_index("ix_cash_tx_currency_day", "cash_transactions", ["currency", "booked_on"])
    op.create_index("ix_cash_transactions_legacy_entry_id", "cash_transactions", ["legacy_entry_id"])
    op.create_index("ix_cash_transactions_adjusts_salary_line_id", "cash_transactions", ["adjusts_salary_line_id"])
    op.create_table(
        "ledger_cutover",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(length=10), nullable=False, server_default="shadow"),
        sa.Column("applied_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("applied_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("went_live_at", sa.DateTime(), nullable=True),
        sa.Column("live_writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("fingerprint_json", sa.Text(), nullable=False, server_default=""),
    )
    # fee payments already have deleted_at; they learn who cancelled them and why
    op.add_column("fee_payments", sa.Column("voided_by", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("fee_payments", sa.Column("void_reason", sa.String(length=300), nullable=False, server_default=""))
    for table in ("fee_charges", "salary_lines"):
        for column in _void_columns():
            op.add_column(table, column)
    # receipts: for a booking of the cash book too; never deleted, only taken out of view
    with op.batch_alter_table("entry_receipts") as batch:
        batch.alter_column("entry_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("transaction_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("removed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("removed_by", sa.String(length=80), nullable=False, server_default=""))
        batch.add_column(sa.Column("remove_reason", sa.String(length=300), nullable=False, server_default=""))
        batch.create_foreign_key("fk_entry_receipts_transaction", "cash_transactions", ["transaction_id"], ["id"], ondelete="RESTRICT")
        batch.create_index("ix_entry_receipts_transaction_id", ["transaction_id"])
        batch.create_check_constraint("ck_entry_receipts_one_owner", "(entry_id IS NOT NULL) <> (transaction_id IS NOT NULL)")
    # the audit log says what changed, from what, to what, and why (the old text stays)
    op.add_column("fee_audit_log", sa.Column("entity_type", sa.String(length=30), nullable=False, server_default=""))
    op.add_column("fee_audit_log", sa.Column("before_json", sa.Text(), nullable=False, server_default=""))
    op.add_column("fee_audit_log", sa.Column("after_json", sa.Text(), nullable=False, server_default=""))
    op.add_column("fee_audit_log", sa.Column("reason", sa.String(length=300), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("fee_audit_log", "reason")
    op.drop_column("fee_audit_log", "after_json")
    op.drop_column("fee_audit_log", "before_json")
    op.drop_column("fee_audit_log", "entity_type")
    with op.batch_alter_table("entry_receipts") as batch:
        batch.drop_constraint("ck_entry_receipts_one_owner", type_="check")
        batch.drop_index("ix_entry_receipts_transaction_id")
        batch.drop_constraint("fk_entry_receipts_transaction", type_="foreignkey")
        batch.drop_column("remove_reason")
        batch.drop_column("removed_by")
        batch.drop_column("removed_at")
        batch.drop_column("transaction_id")
        batch.alter_column("entry_id", existing_type=sa.Uuid(), nullable=False)
    for table in ("salary_lines", "fee_charges"):
        op.drop_column(table, "void_reason")
        op.drop_column(table, "voided_by")
        op.drop_column(table, "voided_at")
    op.drop_column("fee_payments", "void_reason")
    op.drop_column("fee_payments", "voided_by")
    op.drop_table("ledger_cutover")
    op.drop_table("cash_transactions")
