"""One connection between a parent account and a child, kept in both places that need it:

- the link the portals use (`parent_child_links`): the parent sees the child's page, reports, chats ...;
- the father / mother in the child's record (`ChildGuardian.account_id`): the management sees who has an account.

Every way of connecting (the record's account field, an invitation code, the approval of a registration request, a new parent
account made for a child, the admin's link) goes through here, so the two never tell a different story. Whoever registers is
put on the right father / mother of the record: by the relation the invitation was made for, else by the same e-mail, phone or
name as in the registration request; a missing father / mother entry is added from the request.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import Child, ChildGuardian, RegistrationRequest, parent_child_links

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MOTHER_WORDS = {"أم", "الأم", "ام", "الام", "والدة", "الوالدة", "ماما", "mother", "mom", "mum", "mama", "mutter", "mère", "mere"}
FATHER_WORDS = {"أب", "الأب", "اب", "الاب", "والد", "الوالد", "بابا", "father", "dad", "papa", "vater", "père", "pere"}


def new_code() -> str:
    """A short one-time code like K7QM-4XD9 (no confusing 0/O/1/I)."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def relation_of(text: str) -> str:
    """'mother' / 'father' / 'guardian' from what the parent wrote ("الأم", "Vater", "ولي الأمر" ...)."""
    words = {w for w in re.split(r"[\s/،,.\-]+", (text or "").strip().lower()) if w}
    if words & MOTHER_WORDS:
        return "mother"
    if words & FATHER_WORDS:
        return "father"
    return "guardian"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def same_phone(a: str, b: str) -> bool:
    """The same number, with or without the country code (+963 11 ... and 011 ...)."""
    da, db = _digits(a), _digits(b)
    return len(da) >= 7 and len(db) >= 7 and da[-9:] == db[-9:]


def same_person(row: ChildGuardian, email: str, phone: str, name: str) -> bool:
    email = (email or "").strip().lower()
    return bool(
        (email and (row.email or "").strip().lower() == email)
        or same_phone(row.phone or "", phone)
        or (name.strip() and (row.name or "").strip().lower() == name.strip().lower())
    )


def request_of(session: Session, account_id: uuid.UUID) -> RegistrationRequest | None:
    return session.scalar(select(RegistrationRequest).where(RegistrationRequest.account_id == account_id)
                          .order_by(RegistrationRequest.created_at.desc()).limit(1))


def guardians(session: Session, child_id: uuid.UUID) -> list[ChildGuardian]:
    return list(session.scalars(select(ChildGuardian).where(ChildGuardian.child_id == child_id)).all())


def note_guardian(session: Session, child_id: uuid.UUID, req: RegistrationRequest, relation: str = "") -> ChildGuardian | None:
    """The father / mother of the record that the registration request is about: the entry with the same e-mail, phone or name,
    else the entry of the relation, else a new entry (when the relation is still free). Empty phone / e-mail are filled in."""
    rows = guardians(session, child_id)
    wanted = relation or relation_of(req.relationship_to_child)
    row = next((r for r in rows if same_person(r, req.email, req.phone, req.guardian_name)), None)
    if row is None:
        row = next((r for r in rows if r.relation == wanted and r.account_id is None), None)
    if row is None:
        if any(r.relation == wanted for r in rows) or len(rows) >= 2:
            return None  # the record is full: nothing is overwritten
        row = ChildGuardian(child_id=child_id, relation=wanted, name=(req.guardian_name.strip() or "—")[:120])
        session.add(row)
    if not (row.phone or "").strip():
        row.phone = req.phone.strip()[:40]
    if not (row.email or "").strip():
        row.email = req.email.strip()[:254]
    session.flush()
    return row


def attach(session: Session, account_id: uuid.UUID, child_id: uuid.UUID, relation: str = "",
           req: RegistrationRequest | None = None) -> ChildGuardian | None:
    """Puts the account on the right father / mother of the child's record (see the top of this file)."""
    rows = guardians(session, child_id)
    for row in rows:
        if row.account_id == account_id:
            return row
    req = req if req is not None else request_of(session, account_id)
    free = [r for r in rows if r.account_id is None]
    row = next((r for r in free if r.relation == relation), None) if relation else None
    if row is None and req is not None:
        row = next((r for r in free if same_person(r, req.email, req.phone, req.guardian_name)), None)
        if row is None:
            row = note_guardian(session, child_id, req, relation)
            if row is not None and row.account_id not in (None, account_id):
                row = None
    if row is None:
        return None
    row.account_id = account_id
    session.flush()
    return row


def link(session: Session, account_id: uuid.UUID, child_id: uuid.UUID) -> None:
    """The parent account sees this child in the portals."""
    exists = session.execute(select(parent_child_links.c.account_id).where(
        parent_child_links.c.account_id == account_id, parent_child_links.c.child_id == child_id)).first()
    if exists is None:
        session.execute(parent_child_links.insert().values(account_id=account_id, child_id=child_id, confirmed_at=datetime.now(timezone.utc)))


def connect(session: Session, account_id: uuid.UUID, child_id: uuid.UUID, relation: str = "",
            req: RegistrationRequest | None = None) -> ChildGuardian | None:
    link(session, account_id, child_id)
    return attach(session, account_id, child_id, relation, req)


def disconnect(session: Session, account_id: uuid.UUID, child_id: uuid.UUID) -> None:
    session.execute(delete(parent_child_links).where(
        parent_child_links.c.account_id == account_id, parent_child_links.c.child_id == child_id))
    session.execute(update(ChildGuardian).where(ChildGuardian.child_id == child_id, ChildGuardian.account_id == account_id)
                    .values(account_id=None))


def heal(session: Session) -> int:
    """Links made before this module (or by hand) that are missing in the records: each one is put on its father / mother
    when that can be told for sure. Returns how many were put on the records."""
    on_records = set(session.execute(select(ChildGuardian.child_id, ChildGuardian.account_id).where(ChildGuardian.account_id.is_not(None))).all())
    done = 0
    for account_id, child_id in session.execute(select(parent_child_links.c.account_id, parent_child_links.c.child_id)).all():
        if (child_id, account_id) in on_records:
            continue
        if attach(session, account_id, child_id) is not None:
            done += 1
    return done


def child_for_request(session: Session, req: RegistrationRequest, child_id: uuid.UUID | None = None) -> tuple[Child, bool]:
    """The child a registration request is about: the chosen one, else the child on the list with the same name, else a new
    child. Returns the child and whether it was made now."""
    if child_id is not None:
        child = session.scalar(select(Child).where(Child.id == child_id, Child.is_active.is_(True)))
        if child is not None:
            return child, False
    child = session.scalar(select(Child).where(func.lower(func.trim(Child.display_name)) == req.child_name.strip().lower(),
                                               Child.is_active.is_(True)).order_by(Child.created_at).limit(1))
    if child is not None:
        return child, False
    try:
        birth = date.fromisoformat(req.child_birth_date) if req.child_birth_date else None
    except ValueError:
        birth = None
    child = Child(display_name=req.child_name.strip(), birth_date=birth)
    session.add(child)
    session.flush()
    return child, True
