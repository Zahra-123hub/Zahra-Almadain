"""The new accounting: income, expenses, invoices, exchange rates, closed months. New tables only; nothing old is touched here."""

import uuid
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0038_money"
down_revision: str | None = "0037_books_both"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMPS = [
    sa.Column("created_by", sa.String(length=80), nullable=False, server_default=""),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
]


def entry_columns() -> list[sa.Column]:
    return [
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount_other", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("void_reason", sa.String(length=300), nullable=False, server_default=""),
    ]


def upgrade() -> None:
    op.create_table(
        "currency_rates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("syp_per_usd", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_currency_rates_valid_from", "currency_rates", ["valid_from"])
    categories = op.create_table(
        "income_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(length=30), nullable=True, unique=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="100"),
    )
    op.bulk_insert(categories, [
        {"id": uuid.uuid4(), "key": "tuition", "name": "رسوم الروضة", "is_active": True, "position": 1},
        {"id": uuid.uuid4(), "key": "registration", "name": "رسوم التسجيل", "is_active": True, "position": 2},
        {"id": uuid.uuid4(), "key": "extra_fees", "name": "رسوم إضافية", "is_active": True, "position": 3},
        {"id": uuid.uuid4(), "key": "other_income", "name": "إيرادات أخرى", "is_active": True, "position": 4},
    ])
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(length=20), nullable=False, unique=True),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("payer_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("void_reason", sa.String(length=300), nullable=False, server_default=""),
    )
    op.create_index("ix_invoices_issued_on", "invoices", ["issued_on"])
    op.create_index("ix_invoices_child_id", "invoices", ["child_id"])
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_other", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])
    op.create_table(
        "income_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("booked_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("income_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("children.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("payer_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reverses_id", sa.Uuid(), sa.ForeignKey("income_entries.id", ondelete="RESTRICT"), nullable=True),
        *entry_columns(),
    )
    for column in ("booked_on", "category_id", "child_id", "invoice_id"):
        op.create_index(f"ix_income_entries_{column}", "income_entries", [column])
    op.create_table(
        "expense_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("booked_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("recipient", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("salary_month", sa.String(length=7), nullable=True),
        sa.Column("reverses_id", sa.Uuid(), sa.ForeignKey("expense_entries.id", ondelete="RESTRICT"), nullable=True),
        *entry_columns(),
    )
    for column in ("booked_on", "category", "employee_id"):
        op.create_index(f"ix_expense_entries_{column}", "expense_entries", [column])
    op.create_table(
        "month_closings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_by", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("reopen_reason", sa.String(length=300), nullable=False, server_default=""),
    )
    op.create_index("ix_month_closings_year", "month_closings", ["year"])


def downgrade() -> None:
    for table in ("month_closings", "expense_entries", "income_entries", "invoice_items", "invoices", "income_categories", "currency_rates"):
        op.drop_table(table)
