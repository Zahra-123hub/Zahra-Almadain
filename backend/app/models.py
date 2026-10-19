from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Table,
    Uuid,
    func,
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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
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
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


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
