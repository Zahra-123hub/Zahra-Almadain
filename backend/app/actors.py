"""Who is acting in the administration area."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountGrant


@dataclass
class Actor:
    """A platform account working in one role (manager, accountant, admin ...), or the server admin login (no account id)."""

    account_id: uuid.UUID | None
    name: str
    role: str


def has_grant(session: Session, actor: Actor, name: str) -> bool:
    """The administrator may do everything; anybody else needs the explicit grant on their own account."""
    if actor.role == "admin":
        return True
    if actor.account_id is None:
        return False
    return session.scalar(select(AccountGrant.id).where(AccountGrant.account_id == actor.account_id, AccountGrant.grant_name == name)) is not None
