"""Everyday life of a child, for the parents and the kindergarten: the child's page, notes (praise / remark), things to bring,
the week plan of the group, attendance (and absences the parents report), messages between parents and kindergarten, and
the fees (the parents' own invoices from the accounting).

Who may do what: the kindergarten (teacher, management, admin) writes; a parent reads only what belongs to their own children
(the link between parent account and child) and writes only messages and absences for them. Every check is made here, on the server.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app import money
from app.community import accounts_with_role, notify, parents_of
from app.database import get_session
from app.models import (
    Account,
    Attendance,
    BringItem,
    ChatMessage,
    Child,
    ChildGuardian,
    ChildNote,
    Employee,
    Invoice,
    WeekPlanEntry,
    parent_child_links,
)
from app.timeutil import local_today

STAFF = {"teacher", "manager", "admin"}
WEEKDAYS = range(0, 5)  # Sunday ... Thursday
ATTENDANCE = {"present", "absent", "sick", "excused"}
MAX_MESSAGES = 300


def _now() -> datetime:
    """The time of a new row, to the microsecond (two messages in one second keep their order)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NoteIn(BaseModel):
    kind: str = Field(default="note", pattern="^(praise|note)$")
    text: str = Field(min_length=1, max_length=500)


class BringIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(default="", max_length=1000)
    due_on: date | None = None
    class_name: str = Field(default="", max_length=60)  # empty: every group
    child_id: uuid.UUID | None = None  # set: only this child


class PlanEntryIn(BaseModel):
    weekday: int = Field(ge=0, le=4)
    position: int = Field(default=1, ge=1, le=12)
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(default="", max_length=300)


class PlanIn(BaseModel):
    class_name: str = Field(default="", max_length=60)
    entries: list[PlanEntryIn] = Field(default_factory=list, max_length=80)


class MarkIn(BaseModel):
    child_id: uuid.UUID
    status: str = Field(default="", max_length=12)  # "" removes the mark
    note: str = Field(default="", max_length=300)


class AttendanceIn(BaseModel):
    day: date
    entries: list[MarkIn] = Field(max_length=300)


class AbsenceIn(BaseModel):
    day: date
    status: str = Field(default="sick", pattern="^(sick|absent)$")
    note: str = Field(default="", max_length=300)


OFFICE = "office"  # the conversation with the management (no single teacher)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    # the kindergarten side: a teacher's account id, or "office" for the management
    to: str = Field(default=OFFICE, max_length=40, validation_alias=AliasChoices("to", "with"))


class StaffMessageIn(MessageIn):
    child_id: uuid.UUID
    parent_id: uuid.UUID
    to: str = Field(default="", max_length=40, validation_alias=AliasChoices("to", "with"))  # empty: the writer's own conversation


def build_router(get_principal: Callable) -> APIRouter:
    router = APIRouter(tags=["everyday"])

    # ---- who is asking ----------------------------------------------------------------------------------------------------------
    def staff(principal: Any) -> None:
        if not principal.role_names & STAFF:
            raise HTTPException(403, "هذه الصفحة للروضة فقط.")

    def name_of(session: Session, account: Account) -> str:
        person = session.scalar(select(Employee.name).where(Employee.account_id == account.id, Employee.is_active.is_(True)))
        return (person or account.username)[:80]

    def own_child(session: Session, principal: Any, child_id: uuid.UUID) -> Child:
        """A child of this parent (the link between the parent account and the child), still on the list."""
        if "parent" not in principal.role_names:
            raise HTTPException(403, "هذه الصفحة لأولياء الأمور.")
        linked = session.scalar(select(parent_child_links.c.child_id).where(
            parent_child_links.c.account_id == principal.account.id, parent_child_links.c.child_id == child_id))
        child = session.get(Child, child_id) if linked else None
        if child is None or not child.is_active:
            raise HTTPException(404, "الطفل غير موجود.")
        return child

    def any_child(session: Session, child_id: uuid.UUID) -> Child:
        child = session.get(Child, child_id)
        if child is None or not child.is_active:
            raise HTTPException(404, "الطفل غير موجود.")
        return child

    def staff_ids(session: Session) -> list[uuid.UUID]:
        return accounts_with_role(session, "teacher", "manager", "admin")

    # ---- what is sent back ------------------------------------------------------------------------------------------------------
    def note_data(n: ChildNote) -> dict[str, Any]:
        return {"id": str(n.id), "child_id": str(n.child_id), "kind": n.kind, "text": n.text, "author": n.author_name,
                "created_at": n.created_at.isoformat() if n.created_at else None}

    def bring_data(b: BringItem, names: dict[uuid.UUID, str] | None = None) -> dict[str, Any]:
        return {"id": str(b.id), "title": b.title, "body": b.body, "due_on": b.due_on.isoformat() if b.due_on else None,
                "class_name": b.class_name, "child_id": str(b.child_id) if b.child_id else None,
                "child": (names or {}).get(b.child_id, "") if b.child_id else "", "author": b.author_name,
                "created_at": b.created_at.isoformat() if b.created_at else None}

    def plan_data(rows: list[WeekPlanEntry]) -> list[dict[str, Any]]:
        return [{"weekday": r.weekday, "position": r.position, "title": r.title, "detail": r.detail}
                for r in sorted(rows, key=lambda r: (r.weekday, r.position))]

    def message_data(m: ChatMessage, viewer: uuid.UUID | None = None) -> dict[str, Any]:
        return {"id": str(m.id), "body": m.body, "from_parent": m.from_parent, "sender": m.sender_name, "sender_role": m.sender_role,
                "mine": viewer is not None and m.sender_id == viewer, "with": str(m.staff_id) if m.staff_id else OFFICE,
                "read": m.read_at is not None, "created_at": m.created_at.isoformat() if m.created_at else None}

    # ---- chats: one conversation = one child, one parent account and one teacher (or the management) ------------------------
    def supervisor(principal: Any) -> bool:
        """The management (and the admin) see every conversation and may write in each."""
        return bool(principal.role_names & {"manager", "admin"})

    def writer_role(principal: Any) -> str:
        roles = principal.role_names
        return "admin" if "admin" in roles else "manager" if "manager" in roles else "teacher"

    def teacher_accounts(session: Session) -> dict[uuid.UUID, str]:
        """The active teachers with their names (from the staff list, else the user name)."""
        ids = accounts_with_role(session, "teacher")
        if not ids:
            return {}
        names = dict(session.execute(select(Account.id, Account.username).where(Account.id.in_(ids))).all())
        for account_id, name in session.execute(select(Employee.account_id, Employee.name).where(Employee.account_id.in_(ids), Employee.is_active.is_(True))).all():
            names[account_id] = name
        return names

    def side(value: str, session: Session, writing: bool = True) -> uuid.UUID | None:
        """The kindergarten side named by a client: "office" (None) or the id of a teacher (to write: one still working here)."""
        if not value or value == OFFICE:
            return None
        try:
            account_id = uuid.UUID(value)
        except ValueError:
            raise HTTPException(422, "محادثة غير صالحة.")
        if writing and account_id not in teacher_accounts(session):
            raise HTTPException(422, "هذه المعلمة غير موجودة.")
        return account_id

    def thread_filter(child_id: uuid.UUID, parent_id: uuid.UUID, staff_id: uuid.UUID | None) -> list[Any]:
        return [ChatMessage.child_id == child_id, ChatMessage.parent_id == parent_id,
                ChatMessage.staff_id.is_(None) if staff_id is None else ChatMessage.staff_id == staff_id]

    def mark_read(session: Session, where: list[Any], from_parent: bool) -> None:
        session.execute(update(ChatMessage).where(*where, ChatMessage.from_parent.is_(from_parent), ChatMessage.read_at.is_(None))
                        .values(read_at=datetime.now(timezone.utc).replace(tzinfo=None)))

    def thread(session: Session, where: list[Any], viewer: uuid.UUID) -> list[dict[str, Any]]:
        rows = session.scalars(select(ChatMessage).where(*where).order_by(ChatMessage.created_at.desc()).limit(MAX_MESSAGES)).all()
        return [message_data(m, viewer) for m in reversed(rows)]

    def staff_side_for(principal: Any, session: Session, value: str, writing: bool = True) -> tuple[uuid.UUID | None, bool]:
        """Which conversation a kindergarten account opens or writes in, and whether it takes part in it (reads it).
        A teacher only her own; the management every one (its own is the office)."""
        me = principal.account.id
        if supervisor(principal):
            staff_id = me if value == "me" else side(value, session, writing)
            return staff_id, staff_id is None or staff_id == me
        if value not in ("", "me", str(me)):
            raise HTTPException(403, "هذه المحادثة لمعلمة أخرى.")
        return me, True

    def bring_for(session: Session, child: Child) -> list[BringItem]:
        return list(session.scalars(select(BringItem).where(or_(
            BringItem.child_id == child.id,
            (BringItem.child_id.is_(None)) & (or_(BringItem.class_name == "", BringItem.class_name == (child.class_name or ""))),
        )).order_by(BringItem.created_at.desc()).limit(100)).all())

    # =============================================================================================================================
    # parents
    # =============================================================================================================================
    @router.get("/api/platform/parent/children/{child_id}/overview")
    def parent_overview(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        """The child's page: who the child is, and small numbers for the tiles (what is new or open)."""
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        today = local_today()
        week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
        guardians = session.scalars(select(ChildGuardian).where(ChildGuardian.child_id == child.id)).all()
        mark = session.scalar(select(Attendance).where(Attendance.child_id == child.id, Attendance.day == today))
        invoices = [money.invoice_state(i) for i in session.scalars(select(Invoice).where(Invoice.child_id == child.id, Invoice.voided_at.is_(None))).all()]
        return {
            "id": str(child.id), "name": child.display_name, "class_name": child.class_name or "",
            "birth_date": child.birth_date.isoformat() if child.birth_date else None,
            "status": "active" if child.is_active else "left",
            "guardians": [{"relation": g.relation, "name": g.name} for g in guardians],
            "counts": {
                "notes_new": session.scalar(select(func.count()).select_from(ChildNote).where(ChildNote.child_id == child.id, ChildNote.created_at >= week_ago)) or 0,
                "bring_open": sum(1 for b in bring_for(session, child) if b.due_on is None or b.due_on >= today),
                "messages_unread": session.scalar(select(func.count()).select_from(ChatMessage).where(
                    ChatMessage.child_id == child.id, ChatMessage.parent_id == principal.account.id, ChatMessage.from_parent.is_(False), ChatMessage.read_at.is_(None))) or 0,
                "invoices_open": sum(1 for s in invoices if s["status"] in ("open", "partial")),
                "plan_entries": session.scalar(select(func.count()).select_from(WeekPlanEntry).where(WeekPlanEntry.class_name == (child.class_name or ""))) or 0,
            },
            "today": {"day": today.isoformat(), "attendance": mark.status if mark else None},
        }

    @router.get("/api/platform/parent/children/{child_id}/notes")
    def parent_notes(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        rows = session.scalars(select(ChildNote).where(ChildNote.child_id == child.id).order_by(ChildNote.created_at.desc()).limit(200)).all()
        return [note_data(n) for n in rows]

    @router.get("/api/platform/parent/children/{child_id}/bring")
    def parent_bring(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        return [bring_data(b, {child.id: child.display_name}) for b in bring_for(session, child)]

    @router.get("/api/platform/parent/children/{child_id}/plan")
    def parent_plan(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        rows = session.scalars(select(WeekPlanEntry).where(WeekPlanEntry.class_name == (child.class_name or ""))).all()
        return {"class_name": child.class_name or "", "entries": plan_data(list(rows))}

    @router.get("/api/platform/parent/children/{child_id}/attendance")
    def parent_attendance(child_id: uuid.UUID, response: Response, month: str | None = None, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        year, mon = money.parse_month(month, local_today())
        first, last = money.month_range(year, mon)
        rows = session.scalars(select(Attendance).where(Attendance.child_id == child.id, Attendance.day >= first, Attendance.day <= last).order_by(Attendance.day)).all()
        counts = {s: sum(1 for r in rows if r.status == s) for s in ATTENDANCE}
        return {"month": f"{year}-{mon:02d}", "days": [{"day": r.day.isoformat(), "status": r.status, "note": r.note, "by_parent": r.by_parent} for r in rows], "counts": counts}

    @router.post("/api/platform/parent/children/{child_id}/absence", status_code=201)
    def parent_absence(child_id: uuid.UUID, payload: AbsenceIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        """The parents say beforehand that the child will not come (today or a later day)."""
        child = own_child(session, principal, child_id)
        if payload.day < local_today():
            raise HTTPException(422, "يمكن الإبلاغ عن الغياب لليوم أو لأيام قادمة فقط.")
        row = session.scalar(select(Attendance).where(Attendance.child_id == child.id, Attendance.day == payload.day))
        if row is not None and not row.by_parent and row.status == "present":
            raise HTTPException(409, "سجّلت الروضة حضور الطفل في هذا اليوم.")
        if row is None:
            row = Attendance(child_id=child.id, day=payload.day, status=payload.status)
            session.add(row)
        row.status, row.note, row.by_parent = payload.status, payload.note.strip(), True
        row.set_by, row.set_at = principal.account.username[:80], datetime.now(timezone.utc).replace(tzinfo=None)
        notify(session, staff_ids(session), "absence_reported", child.display_name, "attendance")
        session.commit()
        return {"day": row.day.isoformat(), "status": row.status, "note": row.note, "by_parent": True}

    @router.get("/api/platform/parent/children/{child_id}/contacts")
    def parent_contacts(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        """Whom the parents can write to about this child: every teacher and the management, with the last message and the
        number of unread ones; the conversations with messages first, the newest on top."""
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        me = principal.account.id
        rows = session.scalars(select(ChatMessage).where(ChatMessage.child_id == child.id, ChatMessage.parent_id == me)
                               .order_by(ChatMessage.created_at.desc()).limit(2000)).all()
        teachers = teacher_accounts(session)
        contacts: dict[str, dict[str, Any]] = {OFFICE: {"with": OFFICE, "name": "", "role": "office", "last": None, "unread": 0}}
        for account_id, name in sorted(teachers.items(), key=lambda item: item[1]):
            contacts[str(account_id)] = {"with": str(account_id), "name": name, "role": "teacher", "last": None, "unread": 0}
        for m in rows:
            key = str(m.staff_id) if m.staff_id else OFFICE
            item = contacts.get(key)
            if item is None:  # a teacher who has left: her conversation stays readable
                item = contacts[key] = {"with": key, "name": next((r.sender_name for r in rows if r.staff_id == m.staff_id and not r.from_parent), ""),
                                        "role": "teacher", "last": None, "unread": 0, "gone": True}
            if item["last"] is None:
                item["last"] = message_data(m, me)
            if not m.from_parent and m.read_at is None:
                item["unread"] += 1
        talked = sorted((c for c in contacts.values() if c["last"]), key=lambda c: c["last"]["created_at"] or "", reverse=True)
        return talked + [c for c in contacts.values() if not c["last"]]

    @router.get("/api/platform/parent/children/{child_id}/messages")
    def parent_messages(child_id: uuid.UUID, response: Response, to: str = OFFICE, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        me = principal.account.id
        try:
            staff_id = None if to == OFFICE else uuid.UUID(to)
        except ValueError:
            raise HTTPException(422, "محادثة غير صالحة.")
        where = thread_filter(child.id, me, staff_id)
        mark_read(session, where, from_parent=False)
        session.commit()
        return thread(session, where, me)

    @router.post("/api/platform/parent/children/{child_id}/messages", status_code=201)
    def parent_send(child_id: uuid.UUID, payload: MessageIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        child = own_child(session, principal, child_id)
        staff_id = side(payload.to, session)
        message = ChatMessage(child_id=child.id, parent_id=principal.account.id, sender_id=principal.account.id, staff_id=staff_id, sender_role="parent",
                              sender_name=principal.account.username[:80], from_parent=True, body=payload.body.strip(), created_at=_now())
        session.add(message)
        # the teacher of this conversation; a message to the management goes to the management
        notify(session, [staff_id] if staff_id else accounts_with_role(session, "manager", "admin"), "message_new", child.display_name, "messages")
        session.commit()
        return message_data(message, principal.account.id)

    @router.get("/api/platform/parent/children/{child_id}/fees")
    def parent_fees(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        """The invoices of this child from the accounting: what was asked, what was paid, what is still open."""
        response.headers["Cache-Control"] = "no-store"
        child = own_child(session, principal, child_id)
        rows = session.scalars(select(Invoice).where(Invoice.child_id == child.id, Invoice.voided_at.is_(None), Invoice.is_test.is_(False))
                               .order_by(Invoice.issued_on.desc())).all()
        items = []
        for invoice in rows:
            data = money.invoice_dict(invoice, {child.id: child.display_name}, with_payments=True)
            data["payments"] = [p for p in data.get("payments", []) if not p["voided"]]
            items.append(data)
        return {"invoices": items, "open": sum(1 for i in items if i["status"] in ("open", "partial"))}

    # =============================================================================================================================
    # the kindergarten (teacher, management, admin)
    # =============================================================================================================================
    @router.get("/api/platform/staff/children")
    def staff_children(response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Every child on the list with its group and its parent accounts, and the groups (for the forms)."""
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        children = session.scalars(select(Child).where(Child.is_active.is_(True)).order_by(Child.display_name)).all()
        links = session.execute(select(parent_child_links.c.child_id, Account.id, Account.username)
                                .join(Account, Account.id == parent_child_links.c.account_id).where(Account.is_active.is_(True))).all()
        parents: dict[uuid.UUID, list[dict[str, str]]] = {}
        for child_id, account_id, username in links:
            parents.setdefault(child_id, []).append({"id": str(account_id), "username": username})
        groups = sorted({c.class_name or "" for c in children})
        return {
            "children": [{"id": str(c.id), "name": c.display_name, "class_name": c.class_name or "",
                          "birth_date": c.birth_date.isoformat() if c.birth_date else None, "parents": parents.get(c.id, [])} for c in children],
            "groups": groups,
        }

    # ---- notes ------------------------------------------------------------------------------------------------------------------
    @router.get("/api/platform/staff/children/{child_id}/notes")
    def staff_notes(child_id: uuid.UUID, response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        child = any_child(session, child_id)
        return [note_data(n) for n in session.scalars(select(ChildNote).where(ChildNote.child_id == child.id).order_by(ChildNote.created_at.desc()).limit(200)).all()]

    @router.post("/api/platform/staff/children/{child_id}/notes", status_code=201)
    def staff_add_note(child_id: uuid.UUID, payload: NoteIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        staff(principal)
        child = any_child(session, child_id)
        note = ChildNote(child_id=child.id, author_id=principal.account.id, author_name=name_of(session, principal.account), kind=payload.kind, text=payload.text.strip(), created_at=_now())
        session.add(note)
        notify(session, parents_of(session, child.id), "note_" + payload.kind, child.display_name, "notes")
        session.commit()
        return note_data(note)

    @router.delete("/api/platform/staff/notes/{note_id}", status_code=204)
    def staff_delete_note(note_id: uuid.UUID, principal=Depends(get_principal), session: Session = Depends(get_session)) -> Response:
        staff(principal)
        note = session.get(ChildNote, note_id)
        if note is None:
            raise HTTPException(404, "الملاحظة غير موجودة.")
        session.delete(note)
        session.commit()
        return Response(status_code=204)

    # ---- things to bring --------------------------------------------------------------------------------------------------------
    @router.get("/api/platform/staff/bring")
    def staff_bring(response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        rows = session.scalars(select(BringItem).order_by(BringItem.created_at.desc()).limit(200)).all()
        names = dict(session.execute(select(Child.id, Child.display_name).where(Child.id.in_([r.child_id for r in rows if r.child_id]))).all()) if any(r.child_id for r in rows) else {}
        return [bring_data(b, names) for b in rows]

    @router.post("/api/platform/staff/bring", status_code=201)
    def staff_add_bring(payload: BringIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        staff(principal)
        child = any_child(session, payload.child_id) if payload.child_id else None
        item = BringItem(title=payload.title.strip(), body=payload.body.strip(), due_on=payload.due_on, class_name="" if child else payload.class_name.strip(),
                         child_id=child.id if child else None, author_id=principal.account.id, author_name=name_of(session, principal.account), created_at=_now())
        session.add(item)
        if child is not None:
            receivers = parents_of(session, child.id)
        else:
            kids = session.scalars(select(Child.id).where(Child.is_active.is_(True), *( [Child.class_name == item.class_name] if item.class_name else []))).all()
            receivers = [p for k in kids for p in parents_of(session, k)]
        notify(session, receivers, "bring_new", item.title, "bring")
        session.commit()
        return bring_data(item, {child.id: child.display_name} if child else {})

    @router.delete("/api/platform/staff/bring/{item_id}", status_code=204)
    def staff_delete_bring(item_id: uuid.UUID, principal=Depends(get_principal), session: Session = Depends(get_session)) -> Response:
        staff(principal)
        item = session.get(BringItem, item_id)
        if item is None:
            raise HTTPException(404, "غير موجود.")
        session.delete(item)
        session.commit()
        return Response(status_code=204)

    # ---- the week plan ----------------------------------------------------------------------------------------------------------
    @router.get("/api/platform/staff/plan")
    def staff_plan(response: Response, class_name: str = "", principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        rows = session.scalars(select(WeekPlanEntry).where(WeekPlanEntry.class_name == class_name.strip())).all()
        return {"class_name": class_name.strip(), "entries": plan_data(list(rows))}

    @router.put("/api/platform/staff/plan")
    def staff_save_plan(payload: PlanIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Replaces the whole week plan of one group."""
        staff(principal)
        group = payload.class_name.strip()
        for row in session.scalars(select(WeekPlanEntry).where(WeekPlanEntry.class_name == group)).all():
            session.delete(row)
        session.flush()
        rows = [WeekPlanEntry(class_name=group, weekday=e.weekday, position=e.position, title=e.title.strip(), detail=e.detail.strip()) for e in payload.entries]
        session.add_all(rows)
        kids = session.scalars(select(Child.id).where(Child.is_active.is_(True), Child.class_name == group)).all()
        notify(session, [p for k in kids for p in parents_of(session, k)], "plan_changed", group, "plan")
        session.commit()
        return {"class_name": group, "entries": plan_data(rows)}

    # ---- attendance -------------------------------------------------------------------------------------------------------------
    @router.get("/api/platform/staff/attendance")
    def staff_attendance(response: Response, day: date | None = None, class_name: str | None = None, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        wanted = day or local_today()
        query = select(Child).where(Child.is_active.is_(True))
        if class_name is not None and class_name.strip() != "*":
            query = query.where(Child.class_name == class_name.strip())
        children = session.scalars(query.order_by(Child.display_name)).all()
        marks = {m.child_id: m for m in session.scalars(select(Attendance).where(Attendance.day == wanted, Attendance.child_id.in_([c.id for c in children]))).all()} if children else {}
        rows = [{"child_id": str(c.id), "name": c.display_name, "class_name": c.class_name or "",
                 "status": marks[c.id].status if c.id in marks else None, "note": marks[c.id].note if c.id in marks else "",
                 "by_parent": marks[c.id].by_parent if c.id in marks else False} for c in children]
        counts = {s: sum(1 for r in rows if r["status"] == s) for s in ATTENDANCE}
        counts["open"] = sum(1 for r in rows if r["status"] is None)
        return {"day": wanted.isoformat(), "rows": rows, "counts": counts}

    @router.put("/api/platform/staff/attendance")
    def staff_save_attendance(payload: AttendanceIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        staff(principal)
        if payload.day > local_today():
            raise HTTPException(422, "لا يُسجَّل الحضور لأيام قادمة.")
        who = name_of(session, principal.account)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        changed = 0
        for entry in payload.entries:
            if entry.status and entry.status not in ATTENDANCE:
                raise HTTPException(422, "حالة غير صالحة.")
            any_child(session, entry.child_id)
            row = session.scalar(select(Attendance).where(Attendance.child_id == entry.child_id, Attendance.day == payload.day))
            if not entry.status:
                if row is not None:
                    session.delete(row)
                    changed += 1
                continue
            if row is None:
                row = Attendance(child_id=entry.child_id, day=payload.day, status=entry.status)
                session.add(row)
            row.status, row.note, row.by_parent, row.set_by, row.set_at = entry.status, entry.note.strip(), False, who, now
            changed += 1
        session.commit()
        return {"day": payload.day.isoformat(), "changed": changed}

    # ---- messages with the parents ------------------------------------------------------------------------------------------------
    @router.get("/api/platform/staff/conversations")
    def staff_conversations(response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        """One line per conversation (child, parent account, teacher or management), newest first: the last message and how many
        from the parent are unread. A teacher sees her own conversations, the management every one."""
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        me = principal.account.id
        query = select(ChatMessage)
        if not supervisor(principal):
            query = query.where(ChatMessage.staff_id == me)
        rows = session.scalars(query.order_by(ChatMessage.created_at.desc()).limit(3000)).all()
        seen: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID | None], dict[str, Any]] = {}
        for m in rows:
            key = (m.child_id, m.parent_id, m.staff_id)
            item = seen.get(key)
            if item is None:
                item = seen[key] = {"child_id": str(m.child_id), "parent_id": str(m.parent_id), "with": str(m.staff_id) if m.staff_id else OFFICE,
                                    "mine": m.staff_id == me or (m.staff_id is None and supervisor(principal)), "last": message_data(m, me), "unread": 0}
            if m.from_parent and m.read_at is None:
                item["unread"] += 1
        children = dict(session.execute(select(Child.id, Child.display_name).where(Child.id.in_({k[0] for k in seen}))).all()) if seen else {}
        parents = dict(session.execute(select(Account.id, Account.username).where(Account.id.in_({k[1] for k in seen}))).all()) if seen else {}
        teachers = teacher_accounts(session)
        out = []
        for (child_id, parent_id, staff_id), item in seen.items():
            item["child"] = children.get(child_id, "")
            item["parent"] = parents.get(parent_id, "")
            item["staff"] = teachers.get(staff_id, "") if staff_id else ""
            out.append(item)
        return out

    @router.get("/api/platform/staff/conversations/{child_id}/{parent_id}")
    def staff_conversation(child_id: uuid.UUID, parent_id: uuid.UUID, response: Response, to: str = "", principal=Depends(get_principal),
                           session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        """One conversation. Reading it marks the parent's messages as read only for whoever takes part in it (the management
        looking into a teacher's conversation leaves them unread for her)."""
        response.headers["Cache-Control"] = "no-store"
        staff(principal)
        staff_id, takes_part = staff_side_for(principal, session, to, writing=False)
        where = thread_filter(child_id, parent_id, staff_id)
        if takes_part:
            mark_read(session, where, from_parent=True)
            session.commit()
        return thread(session, where, principal.account.id)

    @router.post("/api/platform/staff/messages", status_code=201)
    def staff_send(payload: StaffMessageIn, principal=Depends(get_principal), session: Session = Depends(get_session)) -> dict[str, Any]:
        staff(principal)
        child = any_child(session, payload.child_id)
        if payload.parent_id not in parents_of(session, child.id):
            raise HTTPException(422, "هذا الحساب ليس وليّ أمر هذا الطفل.")
        staff_id, _ = staff_side_for(principal, session, payload.to)
        message = ChatMessage(child_id=child.id, parent_id=payload.parent_id, sender_id=principal.account.id, staff_id=staff_id,
                              sender_role=writer_role(principal), sender_name=name_of(session, principal.account), from_parent=False,
                              body=payload.body.strip(), created_at=_now())
        session.add(message)
        receivers = [payload.parent_id]
        if staff_id is not None and staff_id != principal.account.id:
            receivers.append(staff_id)  # the management wrote in a teacher's conversation: she is told too
        notify(session, receivers, "message_new", child.display_name, "messages")
        session.commit()
        return message_data(message, principal.account.id)

    return router
