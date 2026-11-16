"""A checkable backup of the OLD accounting tables, made before they are removed (migration 0039).

It only reads. Every table is written to one CSV file (receipt files are written next to it, one file each), and a manifest
keeps the number of rows and a checksum per table. `verify` reads the files again and compares them with the manifest and,
when a database is given, with the row counts of the database. Nothing here knows the models: the tables are read as they are,
so the tool keeps working after the old code is gone.

    python -m app.manage finance-backup --out backups/finance-2026-11-15          (make + verify)
    python -m app.manage finance-backup --out backups/finance-2026-11-15 --verify-only
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, func, inspect, select, text
from sqlalchemy.engine import Connection, Engine

OLD_TABLES = (
    "fee_charges", "fee_charge_lines", "fee_payments", "salary_lines", "accounting_entries", "entry_receipts", "exchange_rates",
    "cash_openings", "period_locks", "cash_counts", "cash_transactions", "ledger_cutover", "step_confirmations",
)
FILE_COLUMNS = {"entry_receipts": "contents"}  # binary columns: written as separate files, the CSV keeps their checksum


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return "base64:" + base64.b64encode(value).decode("ascii")
    return str(value)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def make(engine: Engine, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    present = set(inspect(engine).get_table_names())
    meta = MetaData()
    manifest: dict[str, Any] = {"made_at": datetime.now(timezone.utc).isoformat(), "dialect": engine.dialect.name, "tables": {}}
    with engine.connect() as connection:
        for name in OLD_TABLES:
            if name not in present:
                manifest["tables"][name] = {"present": False}
                continue
            table = Table(name, meta, autoload_with=connection)
            columns = [c.name for c in table.columns]
            file_column = FILE_COLUMNS.get(name)
            in_database = connection.execute(select(func.count()).select_from(table)).scalar_one()
            written = 0
            path = out / f"{name}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                for row in connection.execute(select(table)).mappings():
                    values = []
                    for column in columns:
                        value = row[column]
                        if column == file_column and value is not None:
                            folder = out / f"{name}_files"
                            folder.mkdir(exist_ok=True)
                            (folder / str(row["id"])).write_bytes(value)
                            value = "sha256:" + hashlib.sha256(value).hexdigest()
                        values.append(_cell(value))
                    writer.writerow(values)
                    written += 1
            manifest["tables"][name] = {"present": True, "rows_in_database": in_database, "rows_written": written, "columns": columns, "sha256": _sha(path)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def verify(out: Path, engine: Engine | None = None) -> dict[str, Any]:
    """Reads the backup again. ok only when every file is there, unchanged, complete and (with a database) equal in row count."""
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    checked: dict[str, int] = {}
    present = set(inspect(engine).get_table_names()) if engine is not None else set()
    meta = MetaData()
    for name, info in manifest["tables"].items():
        if not info.get("present"):
            continue
        path = out / f"{name}.csv"
        if not path.exists():
            problems.append(f"{name}: file missing")
            continue
        if _sha(path) != info["sha256"]:
            problems.append(f"{name}: file changed since the backup")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        count = max(len(rows) - 1, 0)
        checked[name] = count
        if rows and rows[0] != info["columns"]:
            problems.append(f"{name}: columns differ")
        if count != info["rows_written"] or count != info["rows_in_database"]:
            problems.append(f"{name}: {count} rows in the file, {info['rows_in_database']} in the database at backup time")
        file_column = FILE_COLUMNS.get(name)
        if file_column and rows:
            at, id_at = rows[0].index(file_column), rows[0].index("id")
            for row in rows[1:]:
                if row[at].startswith("sha256:"):
                    stored = out / f"{name}_files" / row[id_at]
                    if not stored.exists() or hashlib.sha256(stored.read_bytes()).hexdigest() != row[at][7:]:
                        problems.append(f"{name}: file of row {row[id_at]} missing or damaged")
        if engine is not None and name in present:
            with engine.connect() as connection:
                now = connection.execute(select(func.count()).select_from(Table(name, meta, autoload_with=connection))).scalar_one()
            if now != count:
                problems.append(f"{name}: the database has {now} rows now, the backup {count}")
    return {"ok": not problems, "problems": problems, "rows": checked, "made_at": manifest["made_at"]}


# children before parents (foreign keys)
DROP_ORDER = (
    "fee_charge_lines", "fee_payments", "fee_charges", "entry_receipts", "cash_transactions", "salary_lines", "accounting_entries",
    "exchange_rates", "cash_openings", "period_locks", "cash_counts", "ledger_cutover", "step_confirmations",
)


def drop_old_tables(bind: Connection, backup_dir: str | None) -> dict[str, Any]:
    """Drops the old accounting tables when that is safe: either they are all empty, or `backup_dir` holds a backup that matches
    the database right now. Otherwise nothing is dropped. Used by migration 0039 and by `manage drop-old-finance`."""
    present = [name for name in DROP_ORDER if name in set(inspect(bind).get_table_names())]
    rows = {name: bind.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one() for name in present}
    if any(rows.values()):
        if not backup_dir:
            return {"dropped": [], "kept": present, "rows": rows, "reason": "old tables hold rows and no checked backup was named"}
        check = verify(Path(backup_dir), bind.engine)
        if not check["ok"]:
            raise RuntimeError("The backup of the old accounting does not match the database: " + "; ".join(check["problems"]))
    for name in present:
        bind.execute(text(f'DROP TABLE "{name}"'))
    return {"dropped": present, "kept": [], "rows": rows}
