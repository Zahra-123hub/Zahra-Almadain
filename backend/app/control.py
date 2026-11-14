"""The control centre: one place to see what happens in the kindergarten (read only, built on the data that already exists).

Nothing here is a second bookkeeping: money comes from the cash book (or, before the switch, from the old sheets), people and
reports from their own tables. What the system cannot know is reported as "not available", never as "fine".
"""

from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app import activity
from app import ledger as book
from app.accounting import legacy_cash_report
from app.community import accounts_with_role
from app.database import get_session
from app.fees import CURRENCIES, ZERO, FeesActor, money, remaining_amount
from app.models import (
    Account, AccountGrant, Child, ChildGuardian, DailyReport, Employee, FeeAuditLog, FeeCharge, FeePayment, LoginAttempt, PortalSession,
    RegistrationRequest, SalaryLine, SystemCheck, TeacherContent, TeacherPost,
)
from app.timeutil import local_day_bounds, local_now, local_today, to_local

GRANTS = ("control.view", "finance.view")


def has_grant(session: Session, actor: FeesActor, name: str) -> bool:
    """The administrator may do everything; anybody else needs the explicit grant on their own account."""
    if actor.role == "admin":
        return True
    if actor.account_id is None:
        return False
    return session.scalar(select(AccountGrant.id).where(AccountGrant.account_id == actor.account_id, AccountGrant.grant_name == name)) is not None


def naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


class GrantIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    grant: str = Field(max_length=40)


# ---- pieces (each returns plain data) --------------------------------------------------------------------------------------------
def people_counts(session: Session, today: date) -> dict[str, int]:
    since = today - timedelta(days=30)
    return {
        "children_active": session.scalar(select(func.count()).select_from(Child).where(Child.is_active.is_(True))) or 0,
        "children_new_30d": session.scalar(select(func.count()).select_from(Child).where(Child.is_active.is_(True), Child.created_at >= local_day_bounds(since)[0])) or 0,
        "children_left_30d": session.scalar(select(func.count()).select_from(Child).where(Child.left_on.is_not(None), Child.left_on >= since)) or 0,
        "employees_active": session.scalar(select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))) or 0,
        "teachers": len(accounts_with_role(session, "teacher")),
        "parents": len(accounts_with_role(session, "parent")),
        "accounts_pending": session.scalar(select(func.count()).select_from(Account).where(Account.approval_status != "active")) or 0,
        "requests_pending": session.scalar(select(func.count()).select_from(RegistrationRequest).where(RegistrationRequest.status == "pending")) or 0,
        "reports_in_review": session.scalar(select(func.count()).select_from(DailyReport).where(DailyReport.status == "submitted")) or 0,
    }


def failed_sign_ins(session: Session, hours: int = 24) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    marks = session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.attempted_at >= since.replace(tzinfo=None))) or 0
    logged = session.scalar(select(func.count()).select_from(FeeAuditLog).where(FeeAuditLog.action == "auth.login.failed", FeeAuditLog.at >= since.replace(tzinfo=None))) or 0
    # the attempts table keeps hashes only (a sign-in may leave one or two marks); the log knows the failures of real accounts
    return max(logged, (marks + 1) // 2)


def open_fees(session: Session) -> dict[str, dict[str, Any]]:
    result = {code: {"amount": ZERO, "children": set()} for code in CURRENCIES}
    charges = session.scalars(select(FeeCharge).where(FeeCharge.voided_at.is_(None)).options(selectinload(FeeCharge.payments))).all()
    for charge in charges:
        left = remaining_amount(charge)
        if left is not None and left > 0:
            result[charge.currency]["amount"] += left
            result[charge.currency]["children"].add(charge.child_id)
    return {code: {"amount": str(money(v["amount"])), "children": len(v["children"])} for code, v in result.items()}


def finance_block(session: Session, today: date) -> dict[str, Any]:
    """Per currency, never added together. Before the cash book is live the old sheets answer."""
    mode = book.ledger_mode(session)
    fees = open_fees(session)
    first, last = date(today.year, today.month, 1), today
    result: dict[str, Any] = {"mode": mode, "source": "cash_book" if mode == "live" else "legacy_sheets", "currencies": {}}
    since = naive_utc(datetime.now(timezone.utc) - timedelta(days=30))
    voided = session.scalar(select(func.count()).select_from(FeeAuditLog).where(FeeAuditLog.domain == "finance", FeeAuditLog.action.like("%void%"), FeeAuditLog.at >= since)) or 0
    for code in CURRENCIES:
        if mode == "live":
            report = book.cash_report(session, code, today)
        else:
            report = legacy_cash_report(session, code, today)
        now = next((m for m in report["months"] if (m["year"], m["month"]) == (today.year, today.month)), None)
        paid_month = session.scalar(
            select(func.coalesce(func.sum(FeePayment.amount), 0)).join(FeeCharge, FeeCharge.id == FeePayment.charge_id)
            .where(FeeCharge.currency == code, FeePayment.deleted_at.is_(None), FeePayment.paid_on >= first, FeePayment.paid_on <= last)
        )
        salaries_month = session.scalar(
            select(func.coalesce(func.sum(SalaryLine.base), 0)).where(SalaryLine.currency == code, SalaryLine.voided_at.is_(None), SalaryLine.paid_on >= first, SalaryLine.paid_on <= last)
        )
        result["currencies"][code] = {
            "balance": report["balance"], "total_income": report["income"], "total_expense": report["expense"],
            "this_month": None if now is None else {"income": now["income"], "expense": now["expense"]},
            "open_fees": fees[code], "payments_this_month": str(money(paid_month)), "salary_base_paid_this_month": str(money(salaries_month)),
        }
    result["cancelled_last_30_days"] = voided
    return result


def system_check(session: Session) -> dict[str, Any]:
    """Runs the check now and stores the real result. Backups cannot be checked from here and are reported as such."""
    started = time.monotonic()
    database_ok, details = False, ""
    try:
        session.execute(text("SELECT 1"))
        database_ok = True
    except Exception as error:  # the answer is "not reachable", whatever the driver says
        details = f"database: {type(error).__name__}"
        session.rollback()
    migrations_ok: bool | None = None
    current = head = ""
    if database_ok:
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head() or ""
            current = session.execute(text("SELECT version_num FROM alembic_version")).scalar() or ""
            migrations_ok = bool(head) and current == head
            if migrations_ok is False:
                details = (details + " migrations behind").strip()
        except Exception:  # a test database has no alembic table: the state simply cannot be determined
            migrations_ok = None
            session.rollback()
    ok = database_ok and migrations_ok is not False
    elapsed = int((time.monotonic() - started) * 1000)
    session.add(SystemCheck(ok=ok, database_ok=database_ok, migrations_ok=migrations_ok, details=details[:500], duration_ms=elapsed))
    session.commit()
    last_ok = session.scalar(select(SystemCheck).where(SystemCheck.ok.is_(True)).order_by(SystemCheck.checked_at.desc()).limit(1))
    failures = session.scalars(select(SystemCheck).where(SystemCheck.ok.is_(False)).order_by(SystemCheck.checked_at.desc()).limit(5)).all()
    return {
        "backend": {"ok": True, "note": "this answer comes from the backend"},
        "database": {"ok": database_ok, "milliseconds": elapsed},
        "migrations": {"ok": migrations_ok, "current": current, "head": head, "known": migrations_ok is not None},
        "last_success_at": None if last_ok is None else last_ok.checked_at.isoformat(),
        "last_success_local": None if last_ok is None else to_local(last_ok.checked_at).isoformat(),
        "recent_failures": [{"at": f.checked_at.isoformat(), "details": f.details} for f in failures],
        "backup": {"available": False, "note": "No backup status source is connected; this is not a statement that backups work."},
        "failed_sign_ins_24h": failed_sign_ins(session),
    }


def task_list(session: Session, today: date, finance_allowed: bool) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []

    def add(kind: str, count: int, priority: str, **extra: Any) -> None:
        if count:
            tasks.append({"kind": kind, "count": count, "priority": priority, **extra})

    counts = people_counts(session, today)
    add("requests_pending", counts["requests_pending"], "medium")
    add("accounts_pending", counts["accounts_pending"], "medium")
    oldest = session.scalar(select(func.min(DailyReport.created_at)).where(DailyReport.status == "submitted"))
    add("reports_in_review", counts["reports_in_review"], "medium",
        oldest_days=None if oldest is None else max(0, (datetime.now(timezone.utc).replace(tzinfo=None) - oldest).days))
    failed = failed_sign_ins(session)
    add("failed_sign_ins", failed if failed >= 3 else 0, "high", hours=24)
    missing = _children_missing_info(session)
    add("children_missing_info", len(missing), "low")
    if finance_allowed and book.is_live(session):
        flags = sum(1 for code in CURRENCIES for m in book.movements(session, code) if m.needs_receipt and m.source == "booking")
        add("expenses_without_receipt", flags, "low")
    return tasks


def _children_missing_info(session: Session) -> list[dict[str, Any]]:
    guardians = {child_id for (child_id,) in session.execute(select(ChildGuardian.child_id).distinct()).all()}
    found: list[dict[str, Any]] = []
    for child in session.scalars(select(Child).where(Child.is_active.is_(True)).order_by(Child.display_name)):
        missing = [name for name, empty in (("birth_date", child.birth_date is None), ("group", not (child.class_name or "").strip()), ("guardian", child.id not in guardians)) if empty]
        if missing:
            found.append({"id": str(child.id), "name": child.display_name, "missing": missing})
    return found


def build_router(guard: Callable[..., FeesActor], admin_guard: Callable[..., FeesActor]) -> APIRouter:
    router = APIRouter(prefix="/api/admin/control", tags=["control-centre"])

    def finance_allowed(session: Session, actor: FeesActor) -> bool:
        return has_grant(session, actor, "finance.view")

    @router.get("/overview")
    def overview(response: Response, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        allowed = finance_allowed(session, actor)
        last_ok = session.scalar(select(SystemCheck).where(SystemCheck.ok.is_(True)).order_by(SystemCheck.checked_at.desc()).limit(1))
        return {
            "today": today.isoformat(),
            "timezone": "Asia/Damascus",
            "people": people_counts(session, today),
            "tasks": task_list(session, today, allowed),
            "finance": finance_block(session, today) if allowed else None,  # money only for those who were given it
            "system": {"last_success_at": None if last_ok is None else last_ok.checked_at.isoformat(), "failed_sign_ins_24h": failed_sign_ins(session)},
        }

    @router.get("/teachers/activity")
    def teachers_activity(
        response: Response, day: date | None = None, actor: FeesActor = Depends(guard), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """Per teacher for one local day: when last seen, reports made or changed, drafts and returned reports still open, files, posts."""
        response.headers["Cache-Control"] = "no-store"
        wanted = day or local_today()
        start, end = local_day_bounds(wanted)
        names = {row.account_id: row.name for row in session.execute(select(Employee.account_id, Employee.name).where(Employee.account_id.is_not(None))).all()}
        rows: list[dict[str, Any]] = []
        for account_id in accounts_with_role(session, "teacher"):
            account = session.get(Account, account_id)
            last_seen = session.scalar(select(func.max(PortalSession.last_seen_at)).where(PortalSession.account_id == account_id))
            made = session.scalar(select(func.count()).select_from(DailyReport).where(DailyReport.author_id == account_id, DailyReport.created_at >= start, DailyReport.created_at < end)) or 0
            changed = session.scalar(select(func.count()).select_from(DailyReport).where(
                DailyReport.author_id == account_id, DailyReport.updated_at >= start, DailyReport.updated_at < end, DailyReport.created_at < start)) or 0
            rows.append({
                "account_id": str(account_id), "name": names.get(account_id) or account.username, "username": account.username,
                "last_seen": None if last_seen is None else last_seen.isoformat(),
                "last_seen_local": None if last_seen is None else to_local(last_seen).isoformat(),
                "active_that_day": bool(last_seen is not None and start <= last_seen < end) or made > 0 or changed > 0,
                "reports_created": made, "reports_changed": changed,
                "reports_submitted_open": session.scalar(select(func.count()).select_from(DailyReport).where(DailyReport.author_id == account_id, DailyReport.status == "submitted")) or 0,
                "drafts_open": session.scalar(select(func.count()).select_from(DailyReport).where(DailyReport.author_id == account_id, DailyReport.status == "draft")) or 0,
                "returned_open": session.scalar(select(func.count()).select_from(DailyReport).where(DailyReport.author_id == account_id, DailyReport.status == "rejected")) or 0,
                "posts": session.scalar(select(func.count()).select_from(TeacherPost).where(TeacherPost.author_id == account_id, TeacherPost.created_at >= start, TeacherPost.created_at < end)) or 0,
                "files_uploaded": session.scalar(select(func.count()).select_from(TeacherContent).where(TeacherContent.owner_id == account_id, TeacherContent.created_at >= start, TeacherContent.created_at < end)) or 0,
            })
        rows.sort(key=lambda r: (not r["active_that_day"], r["name"].lower()))
        return {"day": wanted.isoformat(), "teachers": rows, "active": sum(1 for r in rows if r["active_that_day"])}

    @router.get("/children")
    def children_overview(response: Response, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        since = today - timedelta(days=30)
        groups = session.execute(
            select(Child.class_name, func.count()).where(Child.is_active.is_(True)).group_by(Child.class_name).order_by(Child.class_name)
        ).all()
        recent = naive_utc(datetime.now(timezone.utc) - timedelta(days=30))
        reported = {cid for (cid,) in session.execute(select(DailyReport.child_id).where(DailyReport.status == "published", DailyReport.published_at >= recent).distinct()).all()}
        active = session.scalars(select(Child).where(Child.is_active.is_(True))).all()
        left = session.scalars(select(Child).where(Child.left_on.is_not(None), Child.left_on >= since).order_by(Child.left_on.desc())).all()
        new = [c for c in active if c.created_at and c.created_at >= local_day_bounds(since)[0]]
        return {
            "active": len(active),
            "groups": [{"name": name or "", "children": count} for name, count in groups],
            "new_last_30_days": [{"id": str(c.id), "name": c.display_name, "since": c.created_at.date().isoformat()} for c in new],
            "left_last_30_days": [{"id": str(c.id), "name": c.display_name, "left_on": c.left_on.isoformat()} for c in left],
            "without_published_report_30d": sum(1 for c in active if c.id not in reported),
            "missing_information": _children_missing_info(session),
            "teacher_assignment": "not_used",  # every teacher sees every active child; there is no assignment to report on
        }

    @router.get("/tasks")
    def tasks(response: Response, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        review = session.execute(
            select(DailyReport.id, DailyReport.title, DailyReport.created_at, Child.display_name, Account.username)
            .join(Child, Child.id == DailyReport.child_id).join(Account, Account.id == DailyReport.author_id)
            .where(DailyReport.status == "submitted").order_by(DailyReport.created_at.asc()).limit(50)
        ).all()
        requests = session.execute(
            select(RegistrationRequest.id, RegistrationRequest.guardian_name, RegistrationRequest.child_name)
            .where(RegistrationRequest.status == "pending").order_by(RegistrationRequest.id).limit(50)
        ).all()
        return {
            "summary": task_list(session, today, finance_allowed(session, actor)),
            "reports_in_review": [{"id": str(r[0]), "title": r[1], "child": r[3], "author": r[4], "since": r[2].isoformat() if r[2] else None} for r in review],
            "registration_requests": [{"id": str(r[0]), "guardian": r[1], "child": r[2]} for r in requests],
        }

    @router.get("/activity")
    def activity_feed(
        response: Response, limit: int = 100, domain: str = "all", actor: FeesActor = Depends(guard), session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        """The latest lines of the activity log of every area. Finance lines only for those who may see finance."""
        response.headers["Cache-Control"] = "no-store"
        query = select(FeeAuditLog).order_by(FeeAuditLog.at.desc())
        if domain != "all":
            query = query.where(FeeAuditLog.domain == domain)
        if not finance_allowed(session, actor):
            query = query.where(FeeAuditLog.domain != "finance")
        rows = session.scalars(query.limit(min(max(limit, 1), 500))).all()
        return [{
            "at": r.at.isoformat() if r.at else None, "at_local": to_local(r.at).isoformat() if r.at else None, "actor": r.actor_name, "domain": r.domain,
            "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "reason": r.reason, "details": r.details,
        } for r in rows]

    @router.get("/system")
    def system(response: Response, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return system_check(session)

    # ---- explicit permissions of single accounts (administrator only) ---------------------------------------------------------------
    @router.get("/grants")
    def grants(response: Response, actor: FeesActor = Depends(admin_guard), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.execute(select(AccountGrant, Account.username).join(Account, Account.id == AccountGrant.account_id).order_by(Account.username, AccountGrant.grant_name)).all()
        return [{"id": str(g.id), "username": name, "grant": g.grant_name, "granted_by": g.granted_by, "granted_at": g.granted_at.isoformat() if g.granted_at else None} for g, name in rows]

    @router.post("/grants", status_code=201)
    def add_grant(payload: GrantIn, actor: FeesActor = Depends(admin_guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        if payload.grant not in GRANTS:
            raise HTTPException(422, "Unknown permission.")
        account = session.scalar(select(Account).where(Account.username == payload.username.strip().lower()))
        if account is None:
            raise HTTPException(404, "Account not found.")
        if session.scalar(select(AccountGrant.id).where(AccountGrant.account_id == account.id, AccountGrant.grant_name == payload.grant)) is not None:
            raise HTTPException(409, "The account already has this permission.")
        row = AccountGrant(account_id=account.id, grant_name=payload.grant, granted_by=actor.name[:80])
        session.add(row)
        session.flush()
        activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="account", action="grant.add", entity_type="account", entity_id=account.id,
                        before=None, after={"username": account.username, "grant": payload.grant})
        session.commit()
        return {"id": str(row.id), "username": account.username, "grant": payload.grant}

    @router.delete("/grants/{grant_id}", status_code=204)
    def remove_grant(grant_id: uuid.UUID, actor: FeesActor = Depends(admin_guard), session: Session = Depends(get_session)) -> Response:
        row = session.get(AccountGrant, grant_id)
        if row is None:
            raise HTTPException(404, "Permission not found.")
        account = session.get(Account, row.account_id)
        activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="account", action="grant.remove", entity_type="account", entity_id=row.account_id,
                        before={"username": account.username if account else "", "grant": row.grant_name}, after=None)
        session.delete(row)
        session.commit()
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    return router
