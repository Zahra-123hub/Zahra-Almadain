from __future__ import annotations

import argparse
import getpass
import json
import re
import sys

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import Account, Role

PASSWORD_HASHER = PasswordHash.recommended()
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,80}$")


def create_account(username: str, role_name: str, password: str) -> None:
    normalized_username = username.strip().lower()
    if not USERNAME_RE.fullmatch(normalized_username):
        raise ValueError("Username must contain 3–80 letters, digits, dots, underscores, or hyphens.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")

    with Session(get_engine()) as session:
        role = session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            raise ValueError(f"Unknown role: {role_name}. Run database migrations first.")
        account = Account(
            username=normalized_username,
            password_hash=PASSWORD_HASHER.hash(password),
            roles=[role],
        )
        session.add(account)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError(f"Account already exists: {normalized_username}.") from exc


def run_backup_command(args: argparse.Namespace) -> int:
    """A checkable backup of the old accounting tables (read only). Made and checked before those tables are removed."""
    from pathlib import Path

    from app import finance_backup

    out = Path(args.out)
    engine = get_engine()
    if not args.verify_only:
        made = finance_backup.make(engine, out)
        print(json.dumps({name: info.get("rows_written") for name, info in made["tables"].items()}, indent=2))
    result = finance_backup.verify(out, engine)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 2


def run_drop_command(args: argparse.Namespace) -> int:
    """Removes the old accounting tables after the named backup was checked against the database (see migration 0039)."""
    from app import finance_backup

    with get_engine().begin() as connection:
        result = finance_backup.drop_old_tables(connection, args.backup)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if not result["kept"] else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage platform accounts and the accounting switch.")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("finance-backup", help="Back up the old accounting tables to CSV files and check the backup (read only).")
    backup.add_argument("--out", required=True, help="Folder for the backup files.")
    backup.add_argument("--verify-only", action="store_true", help="Only check a backup that exists against its manifest and the database.")
    drop = commands.add_parser("drop-old-finance", help="Remove the old accounting tables after a checked backup (never without one).")
    drop.add_argument("--backup", required=True, help="Folder of a backup made with finance-backup.")
    create = commands.add_parser("create-account", help="Create an account with a platform role.")
    create.add_argument("--username", required=True)
    create.add_argument("--role", required=True, choices=("admin", "manager", "teacher", "accountant", "parent"))
    args = parser.parse_args()
    if args.command == "finance-backup":
        sys.exit(run_backup_command(args))
    if args.command == "drop-old-finance":
        sys.exit(run_drop_command(args))

    password = getpass.getpass("New password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    try:
        create_account(args.username, args.role, password)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Created {args.role} account: {args.username.strip().lower()}")


if __name__ == "__main__":
    main()
