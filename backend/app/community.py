"""Everyday life of the portals: notifications, management notices, groups, guardians of a child, storage use.

Groups are the class names of the children (`Child.class_name`), so the accounting lists and the groups never disagree.
Notifications carry only a kind and a short subject (a child's name or a title); the portals translate them.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    Account,
    Announcement,
    Child,
    ChildGuardian,
    DailyReport,
    Notification,
    RegistrationRequest,
    Role,
    TeacherContent,
    parent_child_links,
)

MAX_NOTIFICATIONS = 50
MAX_ANNOUNCEMENTS = 20


# ----------------------------------------------------------------------------- helpers used by the other routes
def parents_of(session: Session, child_id: uuid.UUID) -> list[uuid.UUID]:
    return list(session.scalars(select(parent_child_links.c.account_id).where(parent_child_links.c.child_id == child_id)))


def accounts_with_role(session: Session, *roles: str) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(Account.id)
            .join(Account.roles)
            .where(Role.name.in_(roles), Account.is_active.is_(True), Account.approval_status == "active")
            .distinct()
        )
    )


def notify(session: Session, account_ids: Iterable[uuid.UUID], kind: str, subject: str = "", view: str = "") -> None:
    """Queue one notification for each account (without committing)."""
    for account_id in dict.fromkeys(account_ids):
        session.add(Notification(account_id=account_id, kind=kind, subject=subject[:120], view=view))


def notification_data(item: Notification) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "subject": item.subject,
        "view": item.view,
        "read": item.read_at is not None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def announcement_data(item: Announcement) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "body": item.body,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=2000)


class GroupIn(BaseModel):
    class_name: str = Field(default="", max_length=60)


class GroupRenameIn(BaseModel):
    old_name: str = Field(min_length=1, max_length=60)
    new_name: str = Field(min_length=1, max_length=60)


def build_router(get_principal: Callable, require_role: Callable, require_manage: Callable, storage_limit: int) -> APIRouter:
    router = APIRouter()

    # ------------------------------------------------------------------------- notifications (every platform account)
    @router.get("/api/platform/notifications")
    def list_notifications(
        response: Response, principal=Depends(get_principal), session: Session = Depends(get_session)
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        me = principal.account.id
        items = session.scalars(
            select(Notification).where(Notification.account_id == me).order_by(Notification.created_at.desc()).limit(MAX_NOTIFICATIONS)
        ).all()
        unread = session.scalar(
            select(func.count()).select_from(Notification).where(Notification.account_id == me, Notification.read_at.is_(None))
        )
        return {"unread": unread or 0, "items": [notification_data(item) for item in items]}

    @router.post("/api/platform/notifications/read-all", status_code=204)
    def read_all_notifications(principal=Depends(get_principal), session: Session = Depends(get_session)) -> Response:
        session.execute(
            update(Notification)
            .where(Notification.account_id == principal.account.id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        session.commit()
        return Response(status_code=204)

    @router.post("/api/platform/notifications/{notification_id}/read", status_code=204)
    def read_notification(
        notification_id: uuid.UUID, principal=Depends(get_principal), session: Session = Depends(get_session)
    ) -> Response:
        item = session.scalar(
            select(Notification).where(Notification.id == notification_id, Notification.account_id == principal.account.id)
        )
        if item is None:
            raise HTTPException(404, "Notification not found.")
        if item.read_at is None:
            item.read_at = datetime.now(timezone.utc)
            session.commit()
        return Response(status_code=204)

    # ------------------------------------------------------------------------- notices of the management
    @router.get("/api/platform/announcements")
    def list_announcements(
        response: Response, _principal=Depends(get_principal), session: Session = Depends(get_session)
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        items = session.scalars(select(Announcement).order_by(Announcement.created_at.desc()).limit(MAX_ANNOUNCEMENTS)).all()
        return [announcement_data(item) for item in items]

    @router.post("/api/admin/platform/announcements", status_code=201)
    def create_announcement(
        payload: AnnouncementIn, username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> dict[str, Any]:
        title, body = payload.title.strip(), payload.body.strip()
        if not title:
            raise HTTPException(422, "A title is required.")
        author = session.scalar(select(Account.id).where(Account.username == username))
        item = Announcement(author_id=author, title=title, body=body)
        session.add(item)
        session.flush()
        notify(session, accounts_with_role(session, "parent", "teacher"), "announcement", title, "home")
        session.commit()
        session.refresh(item)
        return announcement_data(item)

    @router.delete("/api/admin/platform/announcements/{announcement_id}", status_code=204)
    def delete_announcement(
        announcement_id: uuid.UUID, _username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> Response:
        item = session.get(Announcement, announcement_id)
        if item is None:
            raise HTTPException(404, "Notice not found.")
        session.delete(item)
        session.commit()
        return Response(status_code=204)

    # ------------------------------------------------------------------------- the guardians of a child (parent view)
    @router.get("/api/platform/parent/children/{child_id}/guardians")
    def list_child_guardians(
        child_id: uuid.UUID,
        response: Response,
        principal=Depends(require_role("parent")),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        linked = session.execute(
            select(parent_child_links.c.child_id).where(
                parent_child_links.c.account_id == principal.account.id, parent_child_links.c.child_id == child_id
            )
        ).first()
        if linked is None:
            raise HTTPException(404, "Child profile not found.")
        rows = session.scalars(select(ChildGuardian).where(ChildGuardian.child_id == child_id).order_by(ChildGuardian.relation)).all()
        # only names, the relation and whether the person has a portal account: no phone numbers or e-mail addresses
        return [
            {"relation": row.relation, "name": row.name, "has_account": row.account_id is not None, "is_me": row.account_id == principal.account.id}
            for row in rows
        ]

    # ------------------------------------------------------------------------- storage used by a teacher
    @router.get("/api/platform/teacher/storage")
    def teacher_storage(
        response: Response, principal=Depends(require_role("teacher")), session: Session = Depends(get_session)
    ) -> dict[str, int]:
        response.headers["Cache-Control"] = "no-store"
        used = session.scalar(
            select(func.coalesce(func.sum(TeacherContent.byte_size), 0)).where(TeacherContent.owner_id == principal.account.id)
        )
        return {"used_bytes": int(used or 0), "limit_bytes": storage_limit}

    # ------------------------------------------------------------------------- management: numbers and groups
    @router.get("/api/admin/platform/people")
    def list_people(
        response: Response, _username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> dict[str, list[dict[str, str]]]:
        """Teacher and parent accounts only (names for the assignment lists); no other account is shown to a manager."""
        response.headers["Cache-Control"] = "no-store"
        result: dict[str, list[dict[str, str]]] = {"teachers": [], "parents": []}
        for role, key in (("teacher", "teachers"), ("parent", "parents")):
            rows = session.execute(
                select(Account.id, Account.username)
                .join(Account.roles)
                .where(Role.name == role, Account.is_active.is_(True), Account.approval_status == "active")
                .order_by(Account.username)
            ).all()
            result[key] = [{"id": str(row[0]), "username": row[1]} for row in rows]
        return result

    @router.get("/api/admin/platform/stats")
    def management_stats(
        response: Response, _username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> dict[str, int]:
        response.headers["Cache-Control"] = "no-store"

        def role_count(name: str) -> int:
            return len(accounts_with_role(session, name))

        return {
            "children": session.scalar(select(func.count()).select_from(Child).where(Child.is_active.is_(True))) or 0,
            "parents": role_count("parent"),
            "teachers": role_count("teacher"),
            "groups": session.scalar(
                select(func.count(func.distinct(Child.class_name))).where(Child.is_active.is_(True), Child.class_name != "")
            )
            or 0,
            "pending_requests": session.scalar(
                select(func.count()).select_from(RegistrationRequest).where(RegistrationRequest.status == "pending")
            )
            or 0,
            "reports_in_review": session.scalar(
                select(func.count()).select_from(DailyReport).where(DailyReport.status == "submitted")
            )
            or 0,
        }

    @router.get("/api/admin/platform/groups")
    def list_groups(
        response: Response, _username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.execute(
            select(Child.class_name, func.count())
            .where(Child.is_active.is_(True), Child.class_name != "")
            .group_by(Child.class_name)
            .order_by(Child.class_name)
        ).all()
        return [{"name": name, "children": count} for name, count in rows]

    @router.patch("/api/admin/platform/children/{child_id}/group")
    def set_child_group(
        child_id: uuid.UUID, payload: GroupIn, _username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> dict[str, str]:
        child = session.scalar(select(Child).where(Child.id == child_id, Child.is_active.is_(True)))
        if child is None:
            raise HTTPException(404, "Child profile not found.")
        child.class_name = payload.class_name.strip()
        session.commit()
        return {"id": str(child.id), "class_name": child.class_name}

    @router.post("/api/admin/platform/groups/rename")
    def rename_group(
        payload: GroupRenameIn, _username: str = Depends(require_manage), session: Session = Depends(get_session)
    ) -> dict[str, int]:
        old, new = payload.old_name.strip(), payload.new_name.strip()
        if not old or not new:
            raise HTTPException(422, "Both group names are required.")
        result = session.execute(update(Child).where(Child.class_name == old, Child.is_active.is_(True)).values(class_name=new))
        if not result.rowcount:
            raise HTTPException(404, "Group not found.")
        session.commit()
        return {"children": result.rowcount}

    return router
