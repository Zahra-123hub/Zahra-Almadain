"""Staff master data: employee number, phone, start and end date, notes. Additive; numbers are given to the people already saved."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0035_employee_details"
down_revision: str | None = "0034_account_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("employee_no", sa.String(length=20), nullable=True))
    op.add_column("employees", sa.Column("phone", sa.String(length=40), nullable=False, server_default=""))
    op.add_column("employees", sa.Column("hired_on", sa.Date(), nullable=True))
    op.add_column("employees", sa.Column("left_on", sa.Date(), nullable=True))
    op.add_column("employees", sa.Column("notes", sa.String(length=500), nullable=False, server_default=""))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM employees ORDER BY created_at, name")).fetchall()
    for number, row in enumerate(rows, start=1):
        bind.execute(sa.text("UPDATE employees SET employee_no = :n WHERE id = :i"), {"n": f"M-{number:04d}", "i": row[0]})
    op.create_index("uq_employees_employee_no", "employees", ["employee_no"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_employees_employee_no", table_name="employees")
    for column in ("notes", "left_on", "hired_on", "phone", "employee_no"):
        op.drop_column("employees", column)
