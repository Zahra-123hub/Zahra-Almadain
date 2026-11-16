"""The activity log of the whole platform: who did what, when, from which value to which, and why.

Lines are written by the server inside the request that makes the change (never by a client), and nothing in the program edits
or deletes them. Domains: finance, account, security, report, content, system.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.actors import Actor
from app.database import get_session
from app.models import FeeAuditLog
from app.tables import xlsx_response

DOMAINS = ("finance", "account", "security", "report", "content", "system")


def record(
    session: Session, *, actor_id: uuid.UUID | None, actor_name: str, domain: str, action: str, entity_type: str = "",
    entity_id: Any = "", before: dict[str, Any] | None = None, after: dict[str, Any] | None = None, reason: str = "", details: str = "",
) -> None:
    """Adds one line to the log (committed together with the change that caused it)."""
    def dump(value: dict[str, Any] | None) -> str:
        return "" if value is None else json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)

    session.add(FeeAuditLog(
        at=datetime.now(timezone.utc).replace(tzinfo=None), actor_id=actor_id, actor_name=(actor_name or "?")[:80], action=action[:40],
        entity_id=str(entity_id)[:40], details=(details or f"{entity_type} {reason}".strip())[:1000], domain=domain if domain in DOMAINS else "system",
        entity_type=entity_type[:30], before_json=dump(before), after_json=dump(after), reason=reason[:300],
    ))


def hash_value(secret: str, kind: str, value: str) -> str:
    """An opaque fingerprint (no raw address or browser text is ever stored)."""
    return hmac.new((secret or "unset").encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def describe_device(user_agent: str) -> str:
    """A short label for the kind of device ("Windows · Chrome"), from the browser text. Unknown stays unknown."""
    ua = user_agent or ""
    system = (
        "Android" if "Android" in ua else "iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Windows" if "Windows" in ua
        else "Mac" if "Macintosh" in ua else "Linux" if "Linux" in ua else ""
    )
    if re.search(r"Dart/|okhttp|CFNetwork", ua):
        app = "Zahra+ App"
    else:
        app = "Edge" if "Edg/" in ua else "Chrome" if "Chrome/" in ua else "Firefox" if "Firefox/" in ua else "Safari" if "Safari/" in ua else ""
    return " · ".join(p for p in (system, app) if p)[:80]


def build_router(guard: Callable[..., Actor]) -> APIRouter:
    """Reading the log. The administrator sees every area and everybody; the management sees the money area;
    an accountant sees only their own lines of the money area."""
    router = APIRouter(prefix="/api/admin/activity", tags=["activity"])

    def rows_of(session: Session, actor: Actor, limit: int, actor_name: str, action: str, date_from: date | None, date_to: date | None, q: str, domain: str) -> list[dict[str, Any]]:
        query = select(FeeAuditLog).order_by(FeeAuditLog.at.desc())
        wanted_domain = domain if actor.role == "admin" else "finance"
        if wanted_domain != "all":
            query = query.where(FeeAuditLog.domain == wanted_domain)
        wanted = actor.name if actor.role == "accountant" else actor_name.strip()
        if wanted:
            query = query.where(FeeAuditLog.actor_name == wanted)
        if action.strip():
            query = query.where(FeeAuditLog.action == action.strip())
        if date_from is not None:
            query = query.where(FeeAuditLog.at >= datetime(date_from.year, date_from.month, date_from.day))
        if date_to is not None:
            end = date_to + timedelta(days=1)
            query = query.where(FeeAuditLog.at < datetime(end.year, end.month, end.day))
        if q.strip():
            like = "%" + q.strip().lower().replace("%", "").replace("_", "") + "%"
            query = query.where(or_(func.lower(FeeAuditLog.details).like(like), func.lower(FeeAuditLog.action).like(like), func.lower(FeeAuditLog.actor_name).like(like)))

        def loaded(text: str) -> Any:
            try:
                return json.loads(text) if text else None
            except ValueError:
                return None

        return [
            {"at": entry.at.isoformat() if entry.at else "", "actor": entry.actor_name, "action": entry.action, "domain": entry.domain, "entity_id": entry.entity_id,
             "details": entry.details, "entity_type": entry.entity_type or "", "reason": entry.reason or "", "before": loaded(entry.before_json), "after": loaded(entry.after_json)}
            for entry in session.scalars(query.limit(min(max(limit, 1), 500))).all()
        ]

    @router.get("")
    def read_log(
        response: Response, limit: int = 100, actor_name: str = "", action: str = "", date_from: date | None = None, date_to: date | None = None, q: str = "",
        domain: str = "finance", actor: Actor = Depends(guard), session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        return rows_of(session, actor, limit, actor_name, action, date_from, date_to, q, domain)

    @router.get("/actors")
    def actors(response: Response, domain: str = "finance", actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> list[str]:
        response.headers["Cache-Control"] = "no-store"
        if actor.role == "accountant":
            return [actor.name]
        query = select(FeeAuditLog.actor_name).distinct().order_by(FeeAuditLog.actor_name)
        wanted_domain = domain if actor.role == "admin" else "finance"
        if wanted_domain != "all":
            query = query.where(FeeAuditLog.domain == wanted_domain)
        return [name for (name,) in session.execute(query).all() if name]

    @router.get("/export.xlsx")
    def export(
        actor_name: str = "", action: str = "", date_from: date | None = None, date_to: date | None = None, q: str = "", domain: str = "finance",
        actor: Actor = Depends(guard), session: Session = Depends(get_session),
    ) -> Response:
        entries = rows_of(session, actor, 500, actor_name, action, date_from, date_to, q, domain)
        return xlsx_response("system-log.xlsx", [("Log", ["Time", "User", "Area", "Action", "Entity", "Reason", "Details"],
                             [[e["at"].replace("T", " ")[:16], e["actor"], e["domain"], e["action"], e["entity_id"], e["reason"], e["details"]] for e in entries])], right_to_left=False)

    return router
