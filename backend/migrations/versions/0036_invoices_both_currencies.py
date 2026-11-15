"""Invoices that show US dollars and Syrian pounds together: a frozen rate on the fee line, positions, the real payment currency,
and the reason of a rate. Additive only; no existing row is changed (the backfill is a separate, checked command)."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0036_invoices_both"
down_revision: str | None = "0035_employee_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exchange_rates", sa.Column("reason", sa.String(length=300), nullable=False, server_default=""))
    op.add_column("fee_charges", sa.Column("invoice_no", sa.String(length=20), nullable=True))
    op.add_column("fee_charges", sa.Column("rate_syp_per_usd", sa.Numeric(18, 6), nullable=True))
    op.add_column("fee_charges", sa.Column("rate_date", sa.Date(), nullable=True))
    op.add_column("fee_charges", sa.Column("rate_source", sa.String(length=14), nullable=False, server_default="none"))
    op.create_index("uq_fee_charges_invoice_no", "fee_charges", ["invoice_no"], unique=True)
    op.add_column("fee_payments", sa.Column("paid_currency", sa.String(length=3), nullable=True))
    op.add_column("fee_payments", sa.Column("paid_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("fee_payments", sa.Column("pay_rate", sa.Numeric(18, 6), nullable=True))
    op.create_table(
        "fee_charge_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("charge_id", sa.Uuid(), sa.ForeignKey("fee_charges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_other", sa.Numeric(14, 2), nullable=True),
    )
    op.create_index("ix_fee_charge_lines_charge_id", "fee_charge_lines", ["charge_id"])


def downgrade() -> None:
    op.drop_index("ix_fee_charge_lines_charge_id", table_name="fee_charge_lines")
    op.drop_table("fee_charge_lines")
    for column in ("pay_rate", "paid_amount", "paid_currency"):
        op.drop_column("fee_payments", column)
    op.drop_index("uq_fee_charges_invoice_no", table_name="fee_charges")
    for column in ("rate_source", "rate_date", "rate_syp_per_usd", "invoice_no"):
        op.drop_column("fee_charges", column)
    op.drop_column("exchange_rates", "reason")
