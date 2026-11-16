from __future__ import annotations

import uuid
from datetime import date, datetime

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    LargeBinary,
    String,
    Text,
    Table,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

account_roles = Table(
    "account_roles",
    Base.metadata,
    Column(
        "account_id",
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Uuid(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(35), default="ar", server_default="ar")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    approval_status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    roles: Mapped[list[Role]] = relationship(
        secondary=account_roles, back_populates="accounts", lazy="selectin"
    )


class Child(Base):
    __tablename__ = "children"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(String(120))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    class_name: Mapped[str] = mapped_column(String(60), default="", server_default="")
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # the day the child left (set when the child is taken off the list)


class ChildGuardian(Base):
    """The father and / or the mother (or another guardian) of a child. A child has one or two of them.
    `account_id` ties the person to a parent account of the portal, if they have one."""

    __tablename__ = "child_guardians"
    __table_args__ = (UniqueConstraint("child_id", "relation", name="uq_child_guardian_relation"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    relation: Mapped[str] = mapped_column(String(10))  # "father" | "mother" | "guardian"
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), default="", server_default="")
    email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


parent_child_links = Table(
    "parent_child_links",
    Base.metadata,
    Column(
        "account_id",
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "child_id",
        Uuid(as_uuid=True),
        ForeignKey("children.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("confirmed_at", DateTime(timezone=True), nullable=False),
)

teacher_child_links = Table(
    "teacher_child_links",
    Base.metadata,
    Column(
        "account_id",
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "child_id",
        Uuid(as_uuid=True),
        ForeignKey("children.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("assigned_at", DateTime(timezone=True), nullable=False),
)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(3000))
    language: Mapped[str] = mapped_column(String(35), default="ar", server_default="ar")
    activities: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    meals: Mapped[str] = mapped_column(String(500), default="", server_default="")
    review_note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


class TeacherPost(Base):
    """A teacher's post: scope "general" is seen by every parent, scope "child" only by that child's parents."""

    __tablename__ = "teacher_posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(10), default="post", server_default="post")
    hidden: Mapped[bool] = mapped_column(default=False, server_default="false")
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    child_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(3000), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class TeacherContent(Base):
    __tablename__ = "teacher_content"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("daily_reports.id", ondelete="SET NULL"), index=True, nullable=True
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teacher_posts.id", ondelete="CASCADE"), index=True, nullable=True
    )
    category: Mapped[str] = mapped_column(String(30))
    original_name: Mapped[str] = mapped_column(String(180))
    media_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int]
    contents: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class GuardianInvitation(Base):
    __tablename__ = "guardian_invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("children.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    expires_at: Mapped[datetime] = mapped_column()
    redeemed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guardian_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(40))
    child_name: Mapped[str] = mapped_column(String(120))
    child_birth_date: Mapped[str] = mapped_column(String(10), default="", server_default="")
    relationship_to_child: Mapped[str] = mapped_column(String(40), default="", server_default="")
    notes: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    preferred_language: Mapped[str] = mapped_column(String(35), default="ar", server_default="ar")
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True)
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("guardian_invitations.id", ondelete="SET NULL"), nullable=True
    )
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    registered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Employee(Base):
    """Staff master data (teachers and other employees on the payroll)."""

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    job_title: Mapped[str] = mapped_column(String(80), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # The platform account of this person (teacher / accountant), if they have one.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    # Usual monthly salary, saved once and used to pre-fill / generate the monthly payroll.
    salary: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), default="SYP", server_default="SYP")
    employee_no: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)  # M-0001 ...
    phone: Mapped[str] = mapped_column(String(40), default="", server_default="")
    hired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # set when deactivated; the person stays in old payroll
    notes: Mapped[str] = mapped_column(String(500), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FeeAuditLog(Base):
    __tablename__ = "fee_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    domain: Mapped[str] = mapped_column(String(20), default="finance", server_default="finance", index=True)  # finance | account | security | report | content | system
    entity_type: Mapped[str] = mapped_column(String(30), default="", server_default="")
    before_json: Mapped[str] = mapped_column(Text, default="", server_default="")
    after_json: Mapped[str] = mapped_column(Text, default="", server_default="")
    reason: Mapped[str] = mapped_column(String(300), default="", server_default="")


class PortalSession(Base):
    __tablename__ = "portal_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    token_id: Mapped[str] = mapped_column(String(64), unique=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column()
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # the role this session works in (None = the account's roles all count, as before); the server checks it on every request
    active_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ip_hash: Mapped[str] = mapped_column(String(64), default="", server_default="")  # never the address itself
    user_agent_hash: Mapped[str] = mapped_column(String(64), default="", server_default="")
    device_label: Mapped[str] = mapped_column(String(80), default="", server_default="")  # e.g. "Windows · Chrome"


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username_hash: Mapped[str] = mapped_column(String(64), index=True)
    attempted_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(40), unique=True)
    accounts: Mapped[list[Account]] = relationship(
        secondary=account_roles, back_populates="roles"
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(80), unique=True)
    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions, back_populates="permissions"
    )


class Notification(Base):
    """A short message for one account. `kind` and `subject` are translated by the portal; no private text is stored."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(120), default="", server_default="")
    view: Mapped[str] = mapped_column(String(20), default="", server_default="")
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class Announcement(Base):
    """A notice from the management that every parent and teacher sees on their start page."""

    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class SiteVisit(Base):
    """One opening of a public page. No address, no browser string, no name: only what is needed to count and to see where people come from."""

    __tablename__ = "site_visits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date, index=True)
    path: Mapped[str] = mapped_column(String(80))
    referrer: Mapped[str] = mapped_column(String(80), default="", server_default="")  # the website the visitor came from ("" = direct)
    device: Mapped[str] = mapped_column(String(10))  # mobile | desktop | tablet
    language: Mapped[str] = mapped_column(String(5), default="", server_default="")
    visitor: Mapped[str] = mapped_column(String(32), index=True)  # a fingerprint that changes every day
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DeviceToken(Base):
    """A phone that signed in to the app and may get push messages (one row per device, bound to one account)."""

    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(300), unique=True)
    platform: Mapped[str] = mapped_column(String(10))
    app_version: Mapped[str] = mapped_column(String(20), default="", server_default="")
    language: Mapped[str] = mapped_column(String(5), default="ar", server_default="ar")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SystemCheck(Base):
    """One run of the system check (database reachable, migrations at the newest state). Only real results are stored."""

    __tablename__ = "system_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checked_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    database_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    migrations_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None: could not be determined
    details: Mapped[str] = mapped_column(String(500), default="", server_default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AccountGrant(Base):
    """An explicit permission for ONE account on top of its roles (for example the control centre for a manager)."""

    __tablename__ = "account_grants"
    __table_args__ = (UniqueConstraint("account_id", "grant_name", name="uq_account_grant"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    grant_name: Mapped[str] = mapped_column(String(40))
    granted_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---- the accounting: income, expenses, invoices, rates, closed months -------------------------------------------------------
# Money is Decimal. Every entry keeps what was really paid (amount + currency), the rate it was entered with and the value in
# the other currency; a later rate never changes it. Nothing is deleted: an entry is cancelled (voided_*) or reversed.


class CurrencyRate(Base):
    """1 USD = syp_per_usd SYP, from `valid_from` on. Set by the management; rows are only ever added."""

    __tablename__ = "currency_rates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    syp_per_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    created_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class IncomeCategory(Base):
    """What an income is for. The four built-in ones carry a `key`; the management may add, rename or switch off others."""

    __tablename__ = "income_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    position: Mapped[int] = mapped_column(Integer, default=100, server_default="100")


class Invoice(Base):
    """A claim, not an income. What is paid and what is open is always calculated from the income entries tied to it."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    issued_on: Mapped[date] = mapped_column(Date, index=True)
    child_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("children.id", ondelete="RESTRICT"), nullable=True, index=True)
    payer_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    description: Mapped[str] = mapped_column(String(300), default="", server_default="")
    currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6))  # SYP for one USD, as it was when the invoice was made
    created_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    voided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    voided_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    void_reason: Mapped[str] = mapped_column(String(300), default="", server_default="")
    items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice", cascade="all, delete-orphan", lazy="selectin", order_by="InvoiceItem.position")
    payments: Mapped[list[IncomeEntry]] = relationship(back_populates="invoice", lazy="selectin", order_by="IncomeEntry.booked_on")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    description: Mapped[str] = mapped_column(String(200), default="", server_default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # in the currency of the invoice
    amount_other: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # the same value in the other currency, at the rate of the invoice
    invoice: Mapped[Invoice] = relationship(back_populates="items")


class IncomeEntry(Base):
    """Money that really came in. A payment of an invoice is an income entry tied to that invoice (never entered twice)."""

    __tablename__ = "income_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booked_on: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(300))
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("income_categories.id", ondelete="RESTRICT"), index=True)
    child_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("children.id", ondelete="RESTRICT"), nullable=True, index=True)
    payer_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # what was really paid (negative only for a reversal)
    currency: Mapped[str] = mapped_column(String(3))  # the currency it was really paid in
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6))  # SYP for one USD, as used for this entry
    amount_other: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # the value in the other currency
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True, index=True)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("income_entries.id", ondelete="RESTRICT"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    voided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    voided_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    void_reason: Mapped[str] = mapped_column(String(300), default="", server_default="")
    invoice: Mapped[Invoice | None] = relationship(back_populates="payments")


class ExpenseEntry(Base):
    """Money that was really paid out. A salary is an expense of the category "salaries" tied to a person of the staff and a month."""

    __tablename__ = "expense_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booked_on: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(30), index=True)
    recipient: Mapped[str] = mapped_column(String(120), default="", server_default="")
    employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True, index=True)
    salary_month: Mapped[str | None] = mapped_column(String(7), nullable=True)  # "2026-11": the month the salary is for
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    amount_other: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("expense_entries.id", ondelete="RESTRICT"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    voided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    voided_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    void_reason: Mapped[str] = mapped_column(String(300), default="", server_default="")


class MonthClosing(Base):
    """A month is closed while it has a row here that was not reopened. Who closed and who reopened it is kept."""

    __tablename__ = "month_closings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer)
    closed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    reopened_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reopened_by: Mapped[str] = mapped_column(String(80), default="", server_default="")
    reopen_reason: Mapped[str] = mapped_column(String(300), default="", server_default="")
