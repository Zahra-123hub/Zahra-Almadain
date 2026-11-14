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
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import FeeAuditLog

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
