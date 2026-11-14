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


def run_ledger_command(args: argparse.Namespace) -> int:
    """The switch from the old accounting sheets to the cash book. Never runs by itself: only on purpose, by a person, here."""
    from app import ledger, legacy_migration as migration
    from app.fees import FeesActor
    from app.timeutil import local_today

    actor = FeesActor(None, (args.by or getpass.getuser())[:80], "admin")
    today = local_today()
    with Session(get_engine()) as session:
        try:
            if args.command == "ledger-status":
                row = ledger.cutover_row(session)
                result = {"mode": ledger.ledger_mode(session), "live_writes": row.live_writes if row else 0, "way_back_blockers": migration.blockers_for_rollback(session) if row and row.state == "live" else []}
            elif args.command == "ledger-migrate":
                if args.apply:
                    result = migration.apply(session, actor, today, refresh=args.refresh, go_live=args.go_live)
                else:
                    result = migration.dry_run(session, today)
            elif args.command == "ledger-live":
                result = migration.go_live(session, actor, today)
            elif args.command == "ledger-rollback":
                result = migration.rollback(session, actor)
            else:  # ledger-discard
                result = migration.discard(session, actor)
        except migration.MigrationAborted as exc:
            print(json.dumps({"aborted": True, "reason": str(exc), "report": exc.report}, indent=2, ensure_ascii=False, default=str), file=sys.stderr)
            return 2
    text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    if getattr(args, "report_file", None):
        with open(args.report_file, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"Report written to {args.report_file}")
    else:
        print(text)
    return 0 if result.get("ok", True) else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage platform accounts and the accounting switch.")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("ledger-migrate", help="Compare the old sheets with the cash book (default: only look). --apply writes.")
    migrate.add_argument("--apply", action="store_true", help="Write the taken-over bookings (one transaction; stops at any unexplained difference).")
    migrate.add_argument("--refresh", action="store_true", help="Rebuild the taken-over bookings (only before the cash book is live).")
    migrate.add_argument("--go-live", action="store_true", help="Make the cash book the truth right after applying.")
    migrate.add_argument("--report-file", help="Write the report to this file instead of the screen.")
    migrate.add_argument("--by", help="Who runs this (written to the activity log).")
    for name, text in (("ledger-live", "Switch from shadow to live."), ("ledger-rollback", "Back to the old sheets (only while nothing new exists)."),
                       ("ledger-discard", "Remove the taken-over bookings again (only in shadow)."), ("ledger-status", "Show the state of the switch.")):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--by", help="Who runs this (written to the activity log).")
    create = commands.add_parser("create-account", help="Create an account with a platform role.")
    create.add_argument("--username", required=True)
    create.add_argument("--role", required=True, choices=("admin", "manager", "teacher", "accountant", "parent"))
    args = parser.parse_args()
    if args.command.startswith("ledger-"):
        sys.exit(run_ledger_command(args))

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
