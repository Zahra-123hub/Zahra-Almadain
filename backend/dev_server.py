"""A local test server for the mobile app (never touches the real server or its data).

    cd backend
    python dev_server.py

It starts on http://127.0.0.1:8765 with a local SQLite file (dev.db) and three test accounts:
    teacher  lehrer / Lehrer-Test-2026
    parent   eltern / Eltern-Test-2026   (linked to the child "Test Kind")
    admin    verwaltung / Verwaltung-Test-2026

Run the app against it:
    cd mobile_app
    flutter run -d windows --dart-define=API_BASE=http://127.0.0.1:8765
Delete dev.db to start from scratch.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "Local-Dev-Only-2026-xyz")
os.environ.setdefault("SESSION_SECRET", "local-dev-session-secret-long-enough")

import uvicorn
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_session
from app.models import Account, Child, Permission, Role, parent_child_links, teacher_child_links

DB = Path(__file__).with_name("dev.db")
engine = create_engine(f"sqlite+pysqlite:///{DB}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)


def override_get_session():
    with Session(engine) as session:
        yield session


main.app.dependency_overrides[get_session] = override_get_session
main.app.dependency_overrides[main.optional_session] = override_get_session


def seed() -> None:
    with Session(engine) as session:
        if session.scalar(select(Role).where(Role.name == "parent")) is not None:
            return
        perms = [Permission(name="accounts.manage"), Permission(name="children.manage"), Permission(name="reports.read")]
        admin_role = Role(name="admin", permissions=perms[:2])
        parent_role = Role(name="parent", permissions=[perms[2]])
        teacher_role = Role(name="teacher")
        session.add_all([admin_role, parent_role, teacher_role])
        hasher = main.PASSWORD_HASHER
        teacher = Account(username="lehrer", password_hash=hasher.hash("Lehrer-Test-2026"), roles=[teacher_role])
        parent = Account(username="eltern", password_hash=hasher.hash("Eltern-Test-2026"), roles=[parent_role])
        admin = Account(username="verwaltung", password_hash=hasher.hash("Verwaltung-Test-2026"), roles=[admin_role])
        child = Child(display_name="Test Kind")
        session.add_all([teacher, parent, admin, child])
        session.flush()
        now = datetime.now(timezone.utc)
        session.execute(teacher_child_links.insert().values(account_id=teacher.id, child_id=child.id, assigned_at=now))
        session.execute(parent_child_links.insert().values(account_id=parent.id, child_id=child.id, confirmed_at=now))
        session.commit()


if __name__ == "__main__":
    seed()
    print("Local test server: http://127.0.0.1:8765  (teacher lehrer, parent eltern)")
    uvicorn.run(main.app, host="127.0.0.1", port=8765, log_level="warning")
