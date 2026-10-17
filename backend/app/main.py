from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
FILE_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|gif|mp4|webm)$")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 25 * 1024 * 1024
SESSION_TTL_SECONDS = 8 * 60 * 60


class GitHubError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class GitHubStore:
    def __init__(self) -> None:
        self.owner = os.getenv("GITHUB_OWNER", "Zahra-123hub")
        self.repo = os.getenv("GITHUB_REPO", "Zahra-Almadain")
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.base_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents"

    def require_token(self) -> None:
        if not self.token:
            raise HTTPException(503, "لم يتم إعداد اتصال GitHub على الخادم.")

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        raw: bool = False,
    ) -> httpx.Response:
        self.require_token()
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{path}",
                    headers=headers,
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise GitHubError(504, "انتهت مهلة الاتصال بـ GitHub. حاول مرة أخرى.") from exc
        except httpx.RequestError as exc:
            raise GitHubError(502, "تعذّر الاتصال بـ GitHub من الخادم.") from exc
        if not response.is_success:
            if response.status_code == 401:
                message = "رمز GitHub المخزن على الخادم غير صالح أو منتهي."
            elif response.status_code == 403:
                message = "رمز GitHub يحتاج صلاحية Contents للقراءة والكتابة."
            elif response.status_code == 404:
                message = "لم يتم العثور على المستودع أو الملف في GitHub."
            else:
                message = "تعذّر إكمال العملية مع GitHub."
            raise GitHubError(response.status_code, message)
        return response

    async def get_content(self) -> tuple[dict[str, Any], str]:
        response = await self.request("GET", "content.json")
        try:
            item = response.json()
            decoded = base64.b64decode(item["content"]).decode("utf-8")
            data = json.loads(decoded)
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            raise GitHubError(502, "ملف content.json غير صالح أو تعذّر قراءته.") from exc
        if not isinstance(data, dict):
            raise GitHubError(502, "بنية ملف المحتوى غير صالحة.")
        data.setdefault("settings", {})
        data.setdefault("gallery", [])
        data.setdefault("news", [])
        return data, item["sha"]

    async def put_content(
        self, data: dict[str, Any], sha: str, message: str
    ) -> None:
        contents = base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")
        ).decode("ascii")
        await self.request(
            "PUT",
            "content.json",
            {"message": message, "content": contents, "sha": sha},
        )

    async def put_file(self, name: str, contents: bytes, message: str) -> None:
        await self.request(
            "PUT",
            name,
            {
                "message": message,
                "content": base64.b64encode(contents).decode("ascii"),
            },
        )

    async def get_file(self, name: str) -> httpx.Response:
        return await self.request("GET", name, raw=True)

    async def delete_file(self, name: str) -> None:
        response = await self.request("GET", name)
        sha = response.json()["sha"]
        await self.request(
            "DELETE",
            name,
            {"message": f"حذف {name}", "sha": sha},
        )


store = GitHubStore()
app = FastAPI(title="Zahrat Al-Madayn API", version="1.0.0")
origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "https://zahra-123hub.github.io,http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class SettingsRequest(BaseModel):
    announce: str = ""
    phone: str = ""
    whatsapp: str = ""
    hours: str = ""
    facebook: str = ""
    instagram: str = ""
    email: str = ""
    hide_default_news: bool = Field(default=False, alias="hideDefaultNews")
    hide_default_gallery: bool = Field(default=False, alias="hideDefaultGallery")

    model_config = {"populate_by_name": True}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def create_session_token(username: str, secret: str, now: int | None = None) -> str:
    issued_at = int(time.time()) if now is None else now
    payload = _b64url(
        json.dumps(
            {"sub": username, "exp": issued_at + SESSION_TTL_SECONDS},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = _b64url(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_session_token(
    token: str, secret: str, now: int | None = None
) -> str | None:
    try:
        payload, signature = token.split(".", 1)
        expected = _b64url(
            hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        decoded = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        current_time = int(time.time()) if now is None else now
        if decoded["exp"] <= current_time:
            return None
        return decoded["sub"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


async def require_admin(
    authorization: str | None = Header(default=None),
) -> str:
    secret = os.getenv("SESSION_SECRET", "")
    if not secret:
        raise HTTPException(503, "لم يتم إعداد جلسات المسؤول على الخادم.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "سجّل الدخول إلى لوحة التحكم.")
    username = verify_session_token(authorization[7:], secret)
    if not username:
        raise HTTPException(401, "انتهت جلسة الدخول. سجّل الدخول مرة أخرى.")
    return username


async def update_content(mutator: Any, message: str) -> Any:
    for _ in range(3):
        data, sha = await store.get_content()
        result = mutator(data)
        try:
            await store.put_content(data, sha, message)
            return result
        except GitHubError as exc:
            if exc.status_code not in (409, 422):
                raise
    raise HTTPException(409, "تعارضت تعديلات متزامنة. أعد المحاولة.")


def identify_file(contents: bytes) -> tuple[str, str]:
    if contents.startswith(b"\xff\xd8\xff"):
        return "jpg", "image"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image"
    if contents.startswith((b"GIF87a", b"GIF89a")):
        return "gif", "image"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "webp", "image"
    if len(contents) >= 12 and contents[4:8] == b"ftyp":
        return "mp4", "video"
    if contents.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm", "video"
    raise HTTPException(400, "نوع الملف غير مدعوم.")


async def upload_asset(file: UploadFile, kind: str) -> str:
    limit = MAX_VIDEO_BYTES if kind == "video" else MAX_IMAGE_BYTES
    contents = await file.read(limit + 1)
    if len(contents) > limit:
        raise HTTPException(
            413,
            "حجم الملف يتجاوز الحد المسموح (10 ميغابايت للصورة و25 ميغابايت للفيديو).",
        )
    extension, actual_kind = identify_file(contents)
    if actual_kind != kind:
        raise HTTPException(400, "نوع الملف لا يطابق القسم المحدد.")
    name = f"{secrets.token_hex(16)}.{extension}"
    await store.put_file(name, contents, f"رفع {name}")
    return name


def media_type(name: str) -> str:
    return {
        "jpg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
        "mp4": "video/mp4",
        "webm": "video/webm",
    }[name.rsplit(".", 1)[1]]


@app.exception_handler(GitHubError)
async def github_error_handler(_request: Any, exc: GitHubError) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code if exc.status_code < 500 else 502,
        content={"detail": exc.message},
    )


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
async def login(payload: LoginRequest) -> dict[str, Any]:
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    session_secret = os.getenv("SESSION_SECRET", "")
    if not expected_password or not session_secret:
        raise HTTPException(503, "لم يتم إعداد بيانات دخول المسؤول على الخادم.")
    valid_username = secrets.compare_digest(payload.username, expected_username)
    valid_password = secrets.compare_digest(payload.password, expected_password)
    if not (valid_username and valid_password):
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غير صحيحة.")
    return {
        "access_token": create_session_token(payload.username, session_secret),
        "token_type": "bearer",
        "expires_in": SESSION_TTL_SECONDS,
    }


@app.get("/api/content")
async def public_content() -> dict[str, Any]:
    data, _sha = await store.get_content()
    return data


@app.get("/api/assets/{name}")
async def public_asset(name: str) -> Response:
    if not FILE_RE.fullmatch(name):
        raise HTTPException(404, "الملف غير موجود.")
    response = await store.get_file(name)
    return Response(
        content=response.content,
        media_type=media_type(name),
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/api/admin/content")
async def admin_content(_username: str = Depends(require_admin)) -> dict[str, Any]:
    data, _sha = await store.get_content()
    return data


@app.post("/api/admin/gallery")
async def add_gallery_item(
    file: UploadFile = File(...),
    kind: str = Form(...),
    caption: str = Form(default=""),
    _username: str = Depends(require_admin),
) -> dict[str, Any]:
    if kind not in ("image", "video"):
        raise HTTPException(400, "نوع العنصر غير صالح.")
    name = await upload_asset(file, kind)
    item = {
        "id": secrets.token_hex(8),
        "kind": kind,
        "asset": name,
        "caption": caption.strip()[:120],
        "ts": int(time.time() * 1000),
    }
    await update_content(lambda data: data["gallery"].append(item), "إضافة إلى المعرض")
    return item


@app.patch("/api/admin/gallery/{item_id}")
async def update_gallery_caption(
    item_id: str,
    payload: dict[str, Any],
    _username: str = Depends(require_admin),
) -> dict[str, bool]:
    caption = str(payload.get("caption", "")).strip()[:120]

    def update(data: dict[str, Any]) -> None:
        item = next((entry for entry in data["gallery"] if entry["id"] == item_id), None)
        if item is None:
            raise HTTPException(404, "عنصر المعرض غير موجود.")
        item["caption"] = caption

    await update_content(update, "تعديل تعليق")
    return {}


@app.delete("/api/admin/gallery/{item_id}")
async def delete_gallery_item(
    item_id: str, _username: str = Depends(require_admin)
) -> dict[str, bool]:
    removed: dict[str, Any] = {}

    def update(data: dict[str, Any]) -> None:
        item = next((entry for entry in data["gallery"] if entry["id"] == item_id), None)
        if item is None:
            raise HTTPException(404, "عنصر المعرض غير موجود.")
        removed.update(item)
        data["gallery"] = [entry for entry in data["gallery"] if entry["id"] != item_id]

    await update_content(update, "حذف من المعرض")
    if FILE_RE.fullmatch(str(removed.get("asset", ""))):
        await store.delete_file(removed["asset"])
    return {}


async def news_fields(
    tag: str, title: str, text: str
) -> dict[str, str]:
    title = title.strip()[:120]
    text = text.strip()[:1500]
    if not title or not text:
        raise HTTPException(400, "العنوان والنص مطلوبان.")
    return {"tag": tag.strip()[:30] or "خبر", "title": title, "text": text}


@app.post("/api/admin/news")
async def add_news(
    tag: str = Form(default="خبر"),
    title: str = Form(...),
    text: str = Form(...),
    file: UploadFile | None = File(default=None),
    _username: str = Depends(require_admin),
) -> dict[str, Any]:
    fields = await news_fields(tag, title, text)
    asset = await upload_asset(file, "image") if file and file.filename else ""
    item = {
        "id": secrets.token_hex(8),
        "asset": asset,
        "ts": int(time.time() * 1000),
        **fields,
    }
    await update_content(lambda data: data["news"].append(item), "خبر جديد")
    return item


@app.post("/api/admin/news/{item_id}")
async def update_news(
    item_id: str,
    tag: str = Form(default="خبر"),
    title: str = Form(...),
    text: str = Form(...),
    file: UploadFile | None = File(default=None),
    remove_image: str = Form(default="0"),
    _username: str = Depends(require_admin),
) -> dict[str, bool]:
    fields = await news_fields(tag, title, text)
    new_asset = await upload_asset(file, "image") if file and file.filename else None
    removed: dict[str, Any] = {}

    def update(data: dict[str, Any]) -> None:
        item = next((entry for entry in data["news"] if entry["id"] == item_id), None)
        if item is None:
            raise HTTPException(404, "الخبر غير موجود.")
        removed["asset"] = item.get("asset", "")
        item.update(fields)
        if new_asset is not None:
            item["asset"] = new_asset
        elif remove_image == "1":
            item["asset"] = ""

    await update_content(update, "تعديل خبر")
    if removed.get("asset") and (new_asset is not None or remove_image == "1"):
        await store.delete_file(removed["asset"])
    return {}


@app.delete("/api/admin/news/{item_id}")
async def delete_news(
    item_id: str, _username: str = Depends(require_admin)
) -> dict[str, bool]:
    removed: dict[str, Any] = {}

    def update(data: dict[str, Any]) -> None:
        item = next((entry for entry in data["news"] if entry["id"] == item_id), None)
        if item is None:
            raise HTTPException(404, "الخبر غير موجود.")
        removed.update(item)
        data["news"] = [entry for entry in data["news"] if entry["id"] != item_id]

    await update_content(update, "حذف خبر")
    if FILE_RE.fullmatch(str(removed.get("asset", ""))):
        await store.delete_file(removed["asset"])
    return {}


@app.put("/api/admin/settings")
async def update_settings(
    payload: SettingsRequest, _username: str = Depends(require_admin)
) -> dict[str, Any]:
    settings = {
        "announce": payload.announce.strip()[:200],
        "phone": payload.phone.strip()[:300],
        "whatsapp": re.sub(r"\D", "", payload.whatsapp),
        "hours": payload.hours.strip()[:200],
        "facebook": payload.facebook.strip()[:300],
        "instagram": payload.instagram.strip()[:300],
        "email": payload.email.strip()[:300],
        "hideDefaultNews": payload.hide_default_news,
        "hideDefaultGallery": payload.hide_default_gallery,
    }
    if settings["whatsapp"] and not 8 <= len(settings["whatsapp"]) <= 15:
        raise HTTPException(400, "رقم الواتساب غير صالح.")
    for key in ("facebook", "instagram"):
        if settings[key] and not settings[key].lower().startswith("https://"):
            raise HTTPException(400, "يجب أن يبدأ الرابط بـ https://")
    await update_content(lambda data: data.update(settings=settings), "تعديل الإعدادات")
    return settings
