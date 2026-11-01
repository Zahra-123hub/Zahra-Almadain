"""Who looks at the public website, and who signs in to the portals.

Visitors of the public site are anonymous: they are counted, not known. A visit stores the day, the page, the website the
visitor came from, the kind of device and the language. The address and the browser string are never stored; they are only
mixed into a fingerprint that changes every day (so one person counts once per day, and nobody can be followed from one
day to the next). Robots are not counted. Private areas (portals, admin, api) are never tracked.

Names only exist for accounts: the admin sees who signed in to the portals and when.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Account, PortalSession, SiteVisit

PRIVATE_PREFIXES = ("/admin", "/login", "/parents", "/teachers", "/management", "/api", "/backend")
PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-.%]{0,79}$")
BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|curl|wget|python|httpclient|headless|monitor|uptime|lighthouse|scan", re.I)
MOBILE_RE = re.compile(r"mobi|android|iphone|ipod", re.I)
TABLET_RE = re.compile(r"ipad|tablet", re.I)
MAX_VIEWS_PER_VISITOR_PER_DAY = 100
KEEP_DAYS = 400


def own_hosts() -> set[str]:
    raw = os.getenv("SITE_HOSTS", "zahratalmadain.com,www.zahratalmadain.com,zahra-123hub.github.io,localhost,127.0.0.1")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def device_of(user_agent: str) -> str:
    if TABLET_RE.search(user_agent):
        return "tablet"
    return "mobile" if MOBILE_RE.search(user_agent) else "desktop"


def referrer_host(value: str) -> str:
    """Only the website name of the page the visitor came from; nothing of the address after it. Our own pages count as direct."""
    try:
        host = (urlsplit(value).hostname or "").lower()
    except ValueError:
        return ""
    return "" if not host or host in own_hosts() else host[:80]


def fingerprint(day: date, address: str, user_agent: str) -> str:
    """Changes every day and cannot be turned back into an address: one visitor is counted once a day, never followed over days."""
    secret = os.getenv("SESSION_SECRET", "") or "unset"
    return hmac.new(f"{secret}:{day.isoformat()}".encode(), f"{address}|{user_agent}".encode(), hashlib.sha256).hexdigest()[:24]


def build_router(require_admin: Callable, client_address: Callable[[Request], str]) -> APIRouter:
    router = APIRouter()

    # ------------------------------------------------------------------ the public beacon
    @router.post("/api/track", status_code=204)
    async def track(request: Request, session: Session = Depends(get_session)) -> Response:
        """The public page tells that it was opened. Always answers 204; a bad or unwanted visit is simply not stored."""
        done = Response(status_code=204, headers={"Cache-Control": "no-store"})
        try:
            raw = await request.body()
            data = json.loads(raw[:2000].decode("utf-8")) if raw else None
            if not isinstance(data, dict):  # an empty or odd body is not a visit
                return done
        except (ValueError, UnicodeDecodeError):
            return done
        agent = request.headers.get("user-agent", "")
        if not agent or BOT_RE.search(agent):
            return done
        path = str(data.get("path", "/"))
        try:
            parts = urlsplit(path)
        except ValueError:
            return done
        if parts.scheme or parts.netloc:  # a full address is not a page of this site
            return done
        path = parts.path or "/"
        if not PATH_RE.match(path) or path.startswith(PRIVATE_PREFIXES):
            return done
        language = str(data.get("lang", ""))[:5]
        if language and not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,3})?", language):
            language = ""
        today = datetime.now(timezone.utc).date()
        visitor = fingerprint(today, client_address(request), agent)
        already = session.scalar(select(func.count()).select_from(SiteVisit).where(SiteVisit.day == today, SiteVisit.visitor == visitor)) or 0
        if already >= MAX_VIEWS_PER_VISITOR_PER_DAY:
            return done
        session.add(SiteVisit(
            day=today, path=path, referrer=referrer_host(str(data.get("referrer", ""))), device=device_of(agent),
            language=language.lower(), visitor=visitor,
        ))
        if random.random() < 0.01:  # now and then the old rows go
            session.execute(delete(SiteVisit).where(SiteVisit.day < today - timedelta(days=KEEP_DAYS)))
        session.commit()
        return done

    # ------------------------------------------------------------------ what the admin sees
    @router.get("/api/admin/platform/visits")
    def visits(
        response: Response,
        days: int = 30,
        _username: str = Depends(require_admin),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        days = min(max(days, 1), 365)
        today = datetime.now(timezone.utc).date()
        first = today - timedelta(days=days - 1)
        rows = session.execute(
            select(SiteVisit.day, SiteVisit.path, SiteVisit.referrer, SiteVisit.device, SiteVisit.language, SiteVisit.visitor).where(SiteVisit.day >= first)
        ).all()
        per_day: dict[date, dict[str, Any]] = {first + timedelta(days=n): {"views": 0, "visitors": set()} for n in range(days)}
        pages: Counter[str] = Counter()
        sources: Counter[str] = Counter()
        devices: Counter[str] = Counter()
        languages: Counter[str] = Counter()
        for day, path, source, device, language, visitor in rows:
            per_day[day]["views"] += 1
            per_day[day]["visitors"].add(visitor)
            pages[path] += 1
            sources[source or ""] += 1
            devices[device] += 1
            languages[language or ""] += 1
        series = [{"day": day.isoformat(), "views": value["views"], "visitors": len(value["visitors"])} for day, value in sorted(per_day.items())]

        def window(count: int) -> dict[str, int]:
            part = series[-count:]
            return {"views": sum(item["views"] for item in part), "visitors": sum(item["visitors"] for item in part)}

        # who signed in to the portals (names exist only here)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        sign_ins = session.execute(
            select(Account.username, PortalSession.created_at, Account.id)
            .join(Account, Account.id == PortalSession.account_id)
            .where(PortalSession.created_at >= since.replace(tzinfo=None))
            .order_by(PortalSession.created_at.desc())
        ).all()
        roles = {
            account.id: sorted(role.name for role in account.roles)
            for account in session.scalars(select(Account).where(Account.id.in_({row[2] for row in sign_ins}))).unique().all()
        } if sign_ins else {}
        people: dict[str, dict[str, Any]] = {}
        for username, at, account_id in sign_ins:
            entry = people.setdefault(username, {"username": username, "roles": roles.get(account_id, []), "last_at": at.isoformat() if at else "", "times": 0})
            entry["times"] += 1
        online = session.scalar(
            select(func.count(func.distinct(PortalSession.account_id))).where(
                PortalSession.revoked_at.is_(None),
                PortalSession.created_at >= (datetime.now(timezone.utc) - timedelta(minutes=30)).replace(tzinfo=None),
            )
        ) or 0
        return {
            "days": days,
            "today": window(1), "week": window(min(7, days)), "period": window(days),
            "series": series,
            "pages": [{"path": path, "views": count} for path, count in pages.most_common(10)],
            "sources": [{"host": host, "views": count} for host, count in sources.most_common(10)],
            "devices": {name: devices.get(name, 0) for name in ("mobile", "desktop", "tablet")},
            "languages": [{"lang": name, "views": count} for name, count in languages.most_common(5)],
            "sign_ins": sorted(people.values(), key=lambda item: item["last_at"], reverse=True)[:30],
            "signed_in_recently": online,
        }

    return router
