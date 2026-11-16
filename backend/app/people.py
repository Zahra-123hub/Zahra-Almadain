"""The people of the kindergarten: children with their parents, and the staff. This is the management's work.

The accounting only reads the staff list (to tie a salary to a person) and the children (to tie an income or an invoice to a child);
it never changes them. Nobody is deleted: a child or a person of the staff is taken off the list and stays in everything older.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import activity, pdfs
from app.actors import Actor
from app.database import get_session
from app.models import Account, Child, ChildGuardian, Employee, Role, parent_child_links
from app.timeutil import local_today

CENT = Decimal("0.01")


def cents(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT)


def log(session: Session, actor: Actor, action: str, entity_id: Any, details: str) -> None:
    activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="account", action=action,
                    entity_type=action.split(".")[0], entity_id=entity_id, details=details)


class EmployeeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    job_title: str = Field(default="", max_length=80)
    account_id: uuid.UUID | None = None  # the person's platform account (teacher / accountant)
    salary: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)  # usual monthly salary
    salary_currency: str = Field(default="SYP", pattern="^(USD|SYP)$")
    phone: str = Field(default="", max_length=40)
    hired_on: date | None = None
    notes: str = Field(default="", max_length=500)


class GuardianIn(BaseModel):
    id: uuid.UUID | None = None
    relation: str = Field(pattern="^(father|mother|guardian)$")
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    account_id: uuid.UUID | None = None  # a parent account of the portal, if this person has one


class ChildIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    class_name: str = Field(default="", max_length=60)
    birth_date: date | None = None
    guardians: list[GuardianIn] = Field(min_length=1, max_length=2)  # one parent, or both


def build_router(read_guard: Callable[..., Actor], manage_guard: Callable[..., Actor]) -> APIRouter:
    """read_guard: management, admin and the accountant (who only reads). manage_guard: management and admin."""
    router = APIRouter(prefix="/api/admin/people", tags=["people"])

    # ---- employees ----------------------------------------------------------

    def next_employee_no(session: Session) -> str:
        highest = 0
        for number in session.scalars(select(Employee.employee_no).where(Employee.employee_no.is_not(None))):
            tail = number.rsplit("-", 1)[-1]
            if tail.isdigit():
                highest = max(highest, int(tail))
        return f"M-{highest + 1:04d}"

    def employee_data(e: Employee, usernames: dict[uuid.UUID, str], notes: bool = True) -> dict[str, Any]:
        return {
            "employee_no": e.employee_no or "", "phone": e.phone,
            "hired_on": e.hired_on.isoformat() if e.hired_on else None, "left_on": e.left_on.isoformat() if e.left_on else None,
            "is_active": e.is_active, "notes": e.notes if notes else "",
            "id": str(e.id), "name": e.name, "job_title": e.job_title,
            "salary": None if e.salary is None else str(cents(e.salary)),
            "salary_currency": e.salary_currency,
            "account_id": str(e.account_id) if e.account_id else "",
            "account_username": usernames.get(e.account_id, "") if e.account_id else "",
        }

    def link_account(session: Session, employee: Employee, account_id: uuid.UUID | None) -> None:
        """Ties the person to a teacher/accountant account, or unties them (None)."""
        if account_id is None:
            employee.account_id = None
            return
        account = session.scalar(
            select(Account).join(Account.roles).where(Account.id == account_id, Role.name.in_(("teacher", "accountant")))
        )
        if account is None:
            raise HTTPException(404, "الحساب غير موجود أو ليس حساب معلمة/محاسب.")
        holder = session.scalar(
            select(Employee).where(Employee.account_id == account_id, Employee.id != employee.id)
        )
        if holder is not None:
            if holder.is_active:
                raise HTTPException(409, "هذا الحساب مرتبط بموظف آخر.")
            holder.account_id = None  # a person who was taken off the list gives the account back
            session.flush()
        employee.account_id = account_id

    def employee_by_name(session: Session, name: str, include_removed: bool = False) -> Employee | None:
        """The active person with that name. With include_removed, a person taken off the list earlier is found too,
        so saving the same name again brings the old record back (history, saved salary and account stay linked)."""
        rows = session.scalars(
            select(Employee).where(func.lower(Employee.name) == name.strip().lower())
            .order_by(Employee.is_active.desc(), Employee.created_at)
        ).all()
        active = next((e for e in rows if e.is_active), None)
        if active is not None or not include_removed:
            return active
        return rows[0] if rows else None

    @router.get("/employees")
    def list_employees(
        response: Response,
        _actor: Actor = Depends(read_guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.scalars(select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.name)).all()
        usernames = {
            a.id: a.username
            for a in session.scalars(select(Account).where(Account.id.in_([e.account_id for e in rows if e.account_id])))
        }
        return [employee_data(e, usernames, notes=_actor.role in ("manager", "admin")) for e in rows]

    @router.get("/employees/export.{fmt}")
    def export_employees(
        fmt: str,
        scope: str = "all",
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> Response:
        """The staff list as a signed PDF (management and admin only). A plain output of the central table."""
        if fmt != "pdf" or scope not in ("all", "active"):
            raise HTTPException(422, "التصدير بصيغة PDF فقط، لكل الموظفين أو للفعّالين.")
        query = select(Employee).order_by(Employee.employee_no, Employee.name)
        if scope == "active":
            query = query.where(Employee.is_active.is_(True))
        rows = list(session.scalars(query).all())
        log(session, actor, "employee.export", scope, f"{fmt} {len(rows)}")
        session.commit()
        people = [employee_data(e, {}, notes=False) for e in rows]
        content = pdfs.staff_pdf(people, scope, pdfs.signer_of(actor.name, actor.role))
        return Response(content=content, media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="staff-{scope}-{local_today().isoformat()}.pdf"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @router.get("/staff-accounts")
    def staff_accounts(
        response: Response,
        _actor: Actor = Depends(read_guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        """Teacher and accountant accounts a saved person can be tied to (names only, no personal data)."""
        response.headers["Cache-Control"] = "no-store"
        accounts = session.scalars(
            select(Account)
            .join(Account.roles)
            .where(Role.name.in_(("teacher", "accountant")), Account.is_active.is_(True))
            .order_by(Account.username)
        ).unique().all()
        taken = {
            e.account_id: e.name
            for e in session.scalars(select(Employee).where(Employee.account_id.is_not(None), Employee.is_active.is_(True)))
        }
        return [
            {"id": str(a.id), "username": a.username, "roles": sorted(r.name for r in a.roles if r.name in ("teacher", "accountant")),
             "linked_to": taken.get(a.id, "")}
            for a in accounts
        ]

    @router.post("/employees", status_code=201)
    def create_employee(
        payload: EmployeeIn,
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        existing = employee_by_name(session, payload.name, include_removed=True)
        if existing is not None and existing.is_active:
            raise HTTPException(409, "يوجد موظف بهذا الاسم.")
        if existing is not None:  # the same person again: the old record (and everything tied to it) comes back
            employee = existing
            employee.is_active = True
            employee.left_on = None
            employee.job_title = payload.job_title.strip() or employee.job_title
            if payload.phone.strip():
                employee.phone = payload.phone.strip()
            if payload.hired_on is not None:
                employee.hired_on = payload.hired_on
            if payload.notes.strip():
                employee.notes = payload.notes.strip()
            if payload.salary is not None:
                employee.salary = cents(payload.salary)
                employee.salary_currency = payload.salary_currency
            if "account_id" in payload.model_fields_set:
                link_account(session, employee, payload.account_id)
            log(session, actor, "employee.reactivate", employee.id, "")
            session.commit()
            account = session.get(Account, employee.account_id) if employee.account_id else None
            return employee_data(employee, {account.id: account.username} if account else {})
        employee = Employee(
            name=payload.name.strip(), job_title=payload.job_title.strip(),
            salary=None if payload.salary is None else cents(payload.salary),
            salary_currency=payload.salary_currency,
            employee_no=next_employee_no(session), phone=payload.phone.strip(), hired_on=payload.hired_on, notes=payload.notes.strip(),
        )
        session.add(employee)
        session.flush()
        link_account(session, employee, payload.account_id)
        log(session, actor, "employee.create", employee.id, "")
        session.commit()
        account = session.get(Account, employee.account_id) if employee.account_id else None
        return employee_data(employee, {account.id: account.username} if account else {})

    @router.patch("/employees/{employee_id}")
    def update_employee(
        employee_id: uuid.UUID,
        payload: EmployeeIn,
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        employee = session.get(Employee, employee_id)
        if employee is None or not employee.is_active:
            raise HTTPException(404, "الموظف غير موجود.")
        clash = session.scalar(
            select(Employee.id).where(
                func.lower(Employee.name) == payload.name.strip().lower(),
                Employee.is_active.is_(True),
                Employee.id != employee.id,
            )
        )
        if clash is not None:
            raise HTTPException(409, "يوجد موظف بهذا الاسم.")
        employee.name = payload.name.strip()
        employee.job_title = payload.job_title.strip()
        for field in ("phone", "hired_on", "notes"):  # only touched when the form sends them
            if field in payload.model_fields_set:
                value = getattr(payload, field)
                setattr(employee, field, value.strip() if isinstance(value, str) else value)
        if "salary" in payload.model_fields_set:  # only touched when the form sends it
            employee.salary = None if payload.salary is None else cents(payload.salary)
            employee.salary_currency = payload.salary_currency
        if "account_id" in payload.model_fields_set:  # only touched when the form sends it
            link_account(session, employee, payload.account_id)
        log(session, actor, "employee.update", employee.id, "")
        session.commit()
        account = session.get(Account, employee.account_id) if employee.account_id else None
        return employee_data(employee, {account.id: account.username} if account else {})

    @router.delete("/employees/{employee_id}", status_code=204)
    def remove_employee(
        employee_id: uuid.UUID,
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> Response:
        """Takes the person off the list of saved names; old salary rows keep the name."""
        employee = session.get(Employee, employee_id)
        if employee is None:
            raise HTTPException(404, "الموظف غير موجود.")
        employee.is_active = False
        employee.left_on = employee.left_on or local_today()
        log(session, actor, "employee.remove", employee.id, "")
        session.commit()
        return Response(status_code=204)

    # ---- children and their parents -----------------------------------------

    def check_guardians(guardians: list[GuardianIn]) -> None:
        """A child has one or two guardians; never the same role twice (one father, one mother)."""
        relations = [g.relation for g in guardians]
        if len(relations) != len(set(relations)):
            raise HTTPException(422, "لا يمكن إضافة أب ثانٍ أو أم ثانية. أضف أباً وأماً، أو واحداً منهما فقط.")
        emails = [g.email.strip().lower() for g in guardians if g.email.strip()]
        if len(emails) != len(set(emails)):
            raise HTTPException(422, "البريد الإلكتروني نفسه مكرّر للوالدين.")
        accounts = [g.account_id for g in guardians if g.account_id]
        if len(accounts) != len(set(accounts)):
            raise HTTPException(422, "لا يمكن ربط حساب الدخول نفسه بالأب والأم معاً.")

    def parent_account(session: Session, account_id: uuid.UUID) -> Account:
        account = session.scalar(
            select(Account).join(Account.roles).where(
                Account.id == account_id, Account.is_active.is_(True), Role.name == "parent"
            )
        )
        if account is None:
            raise HTTPException(404, "حساب ولي الأمر غير موجود أو غير مفعّل.")
        return account

    def link_parent(session: Session, account_id: uuid.UUID, child_id: uuid.UUID) -> None:
        """The parent account sees this child in the portal."""
        exists = session.execute(
            select(parent_child_links.c.account_id).where(
                parent_child_links.c.account_id == account_id, parent_child_links.c.child_id == child_id
            )
        ).first()
        if exists is None:
            session.execute(parent_child_links.insert().values(
                account_id=account_id, child_id=child_id, confirmed_at=datetime.now(timezone.utc)))

    def unlink_parent(session: Session, account_id: uuid.UUID, child_id: uuid.UUID) -> None:
        session.execute(delete(parent_child_links).where(
            parent_child_links.c.account_id == account_id, parent_child_links.c.child_id == child_id))

    def child_data(session: Session, child: Child) -> dict[str, Any]:
        rows = session.scalars(
            select(ChildGuardian).where(ChildGuardian.child_id == child.id).order_by(ChildGuardian.relation.desc(), ChildGuardian.created_at)
        ).all()
        names = {
            a.id: a.username
            for a in session.scalars(select(Account).where(Account.id.in_([g.account_id for g in rows if g.account_id]))).all()
        } if any(g.account_id for g in rows) else {}
        return {
            "id": str(child.id), "name": child.display_name, "class_name": child.class_name,
            "birth_date": child.birth_date.isoformat() if child.birth_date else "",
            "guardians": [
                {"id": str(g.id), "relation": g.relation, "name": g.name, "phone": g.phone, "email": g.email,
                 "account_id": str(g.account_id) if g.account_id else "", "account_username": names.get(g.account_id, "")}
                for g in rows
            ],
        }

    def sync_guardians(session: Session, child: Child, wanted: list[GuardianIn]) -> None:
        """Makes the stored parents equal to the list: updates the ones that exist, adds new ones, removes the rest."""
        current = {g.id: g for g in session.scalars(select(ChildGuardian).where(ChildGuardian.child_id == child.id)).all()}
        by_relation = {g.relation: g for g in current.values()}
        keep: set[uuid.UUID] = set()
        for item in wanted:
            row = current.get(item.id) if item.id else None
            if row is None:
                row = by_relation.get(item.relation)  # the same role again: the same person
            old_account = row.account_id if row is not None else None
            if item.account_id:
                parent_account(session, item.account_id)
            if row is None:
                row = ChildGuardian(child_id=child.id, relation=item.relation, name=item.name.strip())
                session.add(row)
            row.relation, row.name = item.relation, item.name.strip()
            row.phone, row.email = item.phone.strip(), item.email.strip()
            row.account_id = item.account_id
            session.flush()
            keep.add(row.id)
            if old_account and old_account != item.account_id:
                unlink_parent(session, old_account, child.id)
            if item.account_id:
                link_parent(session, item.account_id, child.id)
        for row in current.values():
            if row.id not in keep:
                if row.account_id:
                    unlink_parent(session, row.account_id, child.id)
                session.delete(row)
        session.flush()

    def child_by_name(session: Session, name: str, ignore: uuid.UUID | None = None) -> Child | None:
        query = select(Child).where(func.lower(Child.display_name) == name.strip().lower(), Child.is_active.is_(True))
        if ignore is not None:
            query = query.where(Child.id != ignore)
        return session.scalar(query)

    @router.get("/children")
    def list_children(
        response: Response,
        _actor: Actor = Depends(read_guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        children = session.scalars(select(Child).where(Child.is_active.is_(True)).order_by(Child.display_name)).all()
        return [child_data(session, child) for child in children]

    @router.get("/parent-accounts")
    def list_parent_accounts(
        response: Response,
        _actor: Actor = Depends(read_guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        """Parent accounts of the portal that can be tied to a father / mother."""
        response.headers["Cache-Control"] = "no-store"
        accounts = session.scalars(
            select(Account).join(Account.roles).where(Role.name == "parent", Account.is_active.is_(True)).order_by(Account.username)
        ).all()
        return [{"id": str(a.id), "username": a.username} for a in accounts]

    @router.post("/children", status_code=201)
    def create_child(
        payload: ChildIn,
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        check_guardians(payload.guardians)
        if child_by_name(session, payload.name) is not None:
            raise HTTPException(409, "يوجد طفل بهذا الاسم.")
        child = Child(display_name=payload.name.strip(), class_name=payload.class_name.strip(), birth_date=payload.birth_date)
        session.add(child)
        session.flush()
        sync_guardians(session, child, payload.guardians)
        log(session, actor, "child.create", child.id, f"{len(payload.guardians)} ولي أمر")
        session.commit()
        session.refresh(child)
        return child_data(session, child)

    @router.patch("/children/{child_id}")
    def update_child(
        child_id: uuid.UUID,
        payload: ChildIn,
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        child = session.scalar(select(Child).where(Child.id == child_id, Child.is_active.is_(True)))
        if child is None:
            raise HTTPException(404, "الطفل غير موجود.")
        check_guardians(payload.guardians)
        if child_by_name(session, payload.name, ignore=child.id) is not None:
            raise HTTPException(409, "يوجد طفل بهذا الاسم.")
        child.display_name, child.class_name = payload.name.strip(), payload.class_name.strip()
        child.birth_date = payload.birth_date
        sync_guardians(session, child, payload.guardians)
        log(session, actor, "child.update", child.id, f"{len(payload.guardians)} ولي أمر")
        session.commit()
        session.refresh(child)
        return child_data(session, child)

    @router.delete("/children/{child_id}", status_code=204)
    def remove_child(
        child_id: uuid.UUID,
        actor: Actor = Depends(manage_guard),
        session: Session = Depends(get_session),
    ) -> Response:
        """Takes the child off the list; the reports and the bookings of the child stay."""
        child = session.scalar(select(Child).where(Child.id == child_id, Child.is_active.is_(True)))
        if child is None:
            raise HTTPException(404, "الطفل غير موجود.")
        child.is_active = False
        child.left_on = local_today()
        log(session, actor, "child.remove", child.id, "")
        session.commit()
        return Response(status_code=204)

    return router
