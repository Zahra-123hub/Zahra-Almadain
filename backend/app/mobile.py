"""Support for the mobile app: version check (public) and the phones that may get push messages.

The app uses the same sign-in and the same endpoints as the portals. This file only adds what a phone needs besides:
which app version is current / the lowest still allowed, and a place to remember the push token of a signed-in phone.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import DeviceToken

PLATFORMS = {"android", "ios"}
MAX_DEVICES_PER_ACCOUNT = 10


def version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value or "")
    return tuple(int(p) for p in parts[:4]) or (0,)


class DeviceIn(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    platform: str
    app_version: str = Field(default="", max_length=20)
    language: str = Field(default="ar", max_length=5)

class DeviceOut(BaseModel):
    token: str = Field(min_length=20, max_length=300)


def build_router(get_principal: Callable) -> APIRouter:
    router = APIRouter()

    @router.get("/api/app/version")
    def app_version(response: Response, version: str = "") -> dict[str, Any]:
        """Public: the current and the lowest allowed version. Everything comes from the environment of the server."""
        response.headers["Cache-Control"] = "no-store"
        latest = os.getenv("APP_LATEST_VERSION", "")
        minimum = os.getenv("APP_MIN_VERSION", "")
        return {
            "latest": latest,
            "min_supported": minimum,
            "update_required": bool(version and minimum and version_tuple(version) < version_tuple(minimum)),
            "update_available": bool(version and latest and version_tuple(version) < version_tuple(latest)),
            "android_url": os.getenv("APP_ANDROID_URL", ""),
            "ios_url": os.getenv("APP_IOS_URL", ""),
            "released": os.getenv("APP_RELEASED", ""),
        }

    @router.post("/api/platform/devices", status_code=204)
    def register_device(
        payload: DeviceIn, principal=Depends(get_principal), session: Session = Depends(get_session)
    ) -> Response:
        if payload.platform not in PLATFORMS:
            raise HTTPException(422, "Unknown platform.")
        me = principal.account.id
        now = datetime.now(timezone.utc)
        row = session.scalar(select(DeviceToken).where(DeviceToken.token == payload.token))
        if row is None:
            rows = session.scalars(
                select(DeviceToken).where(DeviceToken.account_id == me).order_by(DeviceToken.last_seen_at)
            ).all()
            for old in rows[: max(0, len(rows) - MAX_DEVICES_PER_ACCOUNT + 1)]:
                session.delete(old)
            row = DeviceToken(account_id=me, token=payload.token, platform=payload.platform)
            session.add(row)
        # a phone belongs to the person who signed in last
        row.account_id = me
        row.platform = payload.platform
        row.app_version = payload.app_version
        row.language = payload.language if payload.language in {"ar", "de", "en"} else "ar"
        row.last_seen_at = now
        session.commit()
        return Response(status_code=204)

    @router.post("/api/platform/devices/remove", status_code=204)
    def remove_device(
        payload: DeviceOut, principal=Depends(get_principal), session: Session = Depends(get_session)
    ) -> Response:
        session.execute(
            delete(DeviceToken).where(DeviceToken.token == payload.token, DeviceToken.account_id == principal.account.id)
        )
        session.commit()
        return Response(status_code=204)

    return router
