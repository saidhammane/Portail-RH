#!/usr/bin/env python3
"""Deterministic ZKTeco-like punch API used for local integration tests."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import html
import json
import os
import random
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo


SEED_VERSION = "2"
LOCAL_TIMEZONE = "Africa/Casablanca"
DEFAULT_DB_PATH = "/data/zkteco_mock.db"
DEFAULT_SEED_MONTH = "2026-07"
DEFAULT_API_KEY = "zkteco-demo-key"


@dataclass(frozen=True)
class Employee:
    device_user_id: str
    name: str
    email: str
    department: str
    base_arrival_minute: int
    base_departure_minute: int
    verify_mode: str


EMPLOYEES = (
    Employee("1001", "Ahmed El Mansouri", "ahmed.elmansouri@local.test", "Ressources Humaines", 8 * 60 + 35, 17 * 60 + 35, "face"),
    Employee("1002", "Salma Alaoui", "salma.alaoui@local.test", "Informatique", 8 * 60 + 45, 17 * 60 + 50, "fingerprint"),
    Employee("1003", "Youssef Benali", "youssef.benali@local.test", "Finance & Comptabilite", 8 * 60 + 40, 17 * 60 + 40, "face"),
    Employee("1004", "Mariam Zahra", "mariam.zahra@local.test", "Ressources Humaines", 8 * 60 + 55, 17 * 60 + 45, "fingerprint"),
    Employee("1005", "Khalid Rachidi", "khalid.rachidi@local.test", "Ressources Humaines", 8 * 60 + 50, 17 * 60 + 35, "card"),
    Employee("1006", "Hicham Kettani", "hicham.kettani@local.test", "Informatique", 9 * 60, 18 * 60, "face"),
    Employee("1007", "Leila Fassi", "leila.fassi@local.test", "Informatique", 8 * 60 + 50, 17 * 60 + 55, "fingerprint"),
    Employee("1008", "Souad Idrissi", "souad.idrissi@local.test", "Finance & Comptabilite", 8 * 60 + 45, 17 * 60 + 35, "face"),
    Employee("1009", "Reda Soussi", "reda.soussi@local.test", "Finance & Comptabilite", 9 * 60, 18 * 60, "card"),
)


# These exceptions make the month useful for testing without corrupting otherwise valid pairs.
NON_PRESENCE_DAYS = {
    ("1002", "2026-07-16"): ("business_trip", "Mission hors site"),
    ("1004", "2026-07-13"): ("annual_leave", "Conge annuel"),
    ("1005", "2026-07-06"): ("sick_leave", "Arret maladie"),
    ("1005", "2026-07-07"): ("sick_leave", "Arret maladie"),
    ("1008", "2026-07-20"): ("annual_leave", "Conge annuel"),
    ("1009", "2026-07-27"): ("remote_work", "Teletravail"),
}

LATE_ARRIVALS = {
    ("1004", "2026-07-10"): 48,
    ("1006", "2026-07-08"): 37,
    ("1007", "2026-07-24"): 55,
    ("1009", "2026-07-03"): 42,
}

EARLY_DEPARTURES = {
    ("1001", "2026-07-17"): 75,
    ("1003", "2026-07-10"): 60,
    ("1008", "2026-07-24"): 50,
}

# A single deliberately missing checkout tests error handling in the future Odoo importer.
MISSING_PUNCHES = {("1007", "2026-07-22", "check_out")}


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    serial_number TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    timezone TEXT NOT NULL,
    firmware_version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    device_user_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS punches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_uid TEXT NOT NULL UNIQUE,
    device_serial TEXT NOT NULL,
    device_user_id TEXT NOT NULL,
    punch_datetime_utc TEXT NOT NULL,
    local_datetime TEXT NOT NULL,
    punch_type TEXT NOT NULL CHECK (punch_type IN ('check_in', 'check_out')),
    verify_mode TEXT NOT NULL CHECK (verify_mode IN ('face', 'fingerprint', 'card')),
    work_code TEXT NOT NULL DEFAULT '0',
    FOREIGN KEY (device_serial) REFERENCES devices(serial_number),
    FOREIGN KEY (device_user_id) REFERENCES employees(device_user_id)
);

CREATE INDEX IF NOT EXISTS punches_datetime_idx ON punches(punch_datetime_utc);
CREATE INDEX IF NOT EXISTS punches_user_datetime_idx ON punches(device_user_id, punch_datetime_utc);

CREATE TABLE IF NOT EXISTS simulation_calendar (
    work_date TEXT NOT NULL,
    device_user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    PRIMARY KEY (work_date, device_user_id),
    FOREIGN KEY (device_user_id) REFERENCES employees(device_user_id)
);
"""


def parse_month(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("month must use YYYY-MM format") from exc
    return parsed.year, parsed.month


def deterministic_rng(*parts: str) -> random.Random:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def to_local_datetime(work_date: date, minute_of_day: int, seconds: int) -> datetime:
    hour, minute = divmod(minute_of_day, 60)
    return datetime.combine(work_date, time(hour, minute, seconds), ZoneInfo(LOCAL_TIMEZONE))


def external_uid(device_user_id: str, punch_at: datetime, punch_type: str) -> str:
    raw = f"ZK-MA-CASA-01|{device_user_id}|{punch_at.isoformat()}|{punch_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24].upper()


def reset_seed_tables(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM punches")
    connection.execute("DELETE FROM simulation_calendar")
    connection.execute("DELETE FROM employees")
    connection.execute("DELETE FROM devices")
    connection.execute("DELETE FROM metadata")
    connection.execute("DELETE FROM sqlite_sequence WHERE name = 'punches'")


def seed_database(connection: sqlite3.Connection, seed_month: str) -> None:
    year, month = parse_month(seed_month)
    reset_seed_tables(connection)
    connection.execute(
        """
        INSERT INTO devices
            (id, serial_number, name, ip_address, timezone, firmware_version, active)
        VALUES
            (1, 'ZK-MA-CASA-01', 'Siege Casablanca - Entree principale',
             '192.168.10.45', ?, 'Ver 6.60 Apr 18 2025', 1)
        """,
        (LOCAL_TIMEZONE,),
    )
    connection.executemany(
        """
        INSERT INTO employees
            (device_user_id, name, email, department, active)
        VALUES (?, ?, ?, ?, 1)
        """,
        [(employee.device_user_id, employee.name, employee.email, employee.department) for employee in EMPLOYEES],
    )

    holiday_dates = {date(year, month, 30)} if (year, month) == (2026, 7) else set()
    final_day = calendar.monthrange(year, month)[1]

    for day in range(1, final_day + 1):
        work_date = date(year, month, day)
        date_key = work_date.isoformat()
        for employee in EMPLOYEES:
            exception = NON_PRESENCE_DAYS.get((employee.device_user_id, date_key))
            if work_date.weekday() >= 5:
                status, note = "weekend", None
            elif work_date in holiday_dates:
                status, note = "public_holiday", "Fete du Trone"
            elif exception:
                status, note = exception
            else:
                status, note = "present", None

            connection.execute(
                "INSERT INTO simulation_calendar(work_date, device_user_id, status, note) VALUES (?, ?, ?, ?)",
                (date_key, employee.device_user_id, status, note),
            )
            if status != "present":
                continue

            rng = deterministic_rng(seed_month, date_key, employee.device_user_id)
            arrival_minute = employee.base_arrival_minute + rng.randint(-11, 13)
            departure_minute = employee.base_departure_minute + rng.randint(-12, 18)
            arrival_minute += LATE_ARRIVALS.get((employee.device_user_id, date_key), 0)
            departure_minute -= EARLY_DEPARTURES.get((employee.device_user_id, date_key), 0)

            for punch_type, minute_of_day in (
                ("check_in", arrival_minute),
                ("check_out", departure_minute),
            ):
                if (employee.device_user_id, date_key, punch_type) in MISSING_PUNCHES:
                    continue
                local_at = to_local_datetime(work_date, minute_of_day, rng.randint(0, 59))
                utc_at = local_at.astimezone(timezone.utc)
                connection.execute(
                    """
                    INSERT INTO punches
                        (external_uid, device_serial, device_user_id, punch_datetime_utc,
                         local_datetime, punch_type, verify_mode, work_code)
                    VALUES (?, 'ZK-MA-CASA-01', ?, ?, ?, ?, ?, '0')
                    """,
                    (
                        external_uid(employee.device_user_id, local_at, punch_type),
                        employee.device_user_id,
                        utc_at.isoformat().replace("+00:00", "Z"),
                        local_at.isoformat(),
                        punch_type,
                        employee.verify_mode,
                    ),
                )

    connection.executemany(
        "INSERT INTO metadata(key, value) VALUES (?, ?)",
        (
            ("seed_version", SEED_VERSION),
            ("seed_month", seed_month),
            ("timezone", LOCAL_TIMEZONE),
            ("generated_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        ),
    )


def initialize_database(db_path: str, seed_month: str, reset: bool = False) -> None:
    parse_month(seed_month)
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
        must_seed = reset or metadata.get("seed_version") != SEED_VERSION or metadata.get("seed_month") != seed_month
        if must_seed:
            seed_database(connection, seed_month)
        connection.commit()


def dict_rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


class ZKTecoMockHandler(BaseHTTPRequestHandler):
    server_version = "ZKTecoMock/1.0"

    @property
    def config(self) -> dict[str, str]:
        return self.server.config  # type: ignore[attr-defined]

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format_string % args}")

    def send_json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status: HTTPStatus, body: str) -> None:
        encoded_body = body.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded_body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded_body)

    def require_authentication(self) -> bool:
        supplied_key = self.headers.get("X-API-Key", "")
        if supplied_key != self.config["api_key"]:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid_api_key"})
            return False
        return True

    def db_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config["db_path"])
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok", "service": "zkteco-mock-api"})
            return
        if parsed.path == "/demo":
            self.get_demo(parse_qs(parsed.query))
            return
        if not self.require_authentication():
            return

        try:
            if parsed.path == "/api/v1/devices":
                self.get_devices()
            elif parsed.path == "/api/v1/employees":
                self.get_employees()
            elif parsed.path == "/api/v1/punches":
                self.get_punches(parse_qs(parsed.query))
            elif parsed.path == "/api/v1/stats":
                self.get_stats()
            else:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(exc)})
        except sqlite3.Error as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "database_error", "message": str(exc)})

    def get_demo(self, query: dict[str, list[str]]) -> None:
        """Browser-friendly, local-only view of the seeded simulator data."""
        after_id = int(query.get("after_id", ["0"])[0])
        if after_id < 0:
            raise ValueError("after_id must be zero or greater")
        limit = 50
        with closing(self.db_connection()) as connection:
            metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
            total = connection.execute("SELECT COUNT(*) FROM punches").fetchone()[0]
            rows = dict_rows(
                connection.execute(
                    """
                    SELECT id, device_user_id, local_datetime, punch_type, verify_mode, external_uid
                      FROM punches
                     WHERE id > ?
                     ORDER BY id
                     LIMIT ?
                    """,
                    (after_id, limit + 1),
                )
            )
        has_more = len(rows) > limit
        rows = rows[:limit]
        row_html = "".join(
            "<tr>"
            f"<td>{row['id']}</td>"
            f"<td>{html.escape(row['device_user_id'])}</td>"
            f"<td>{html.escape(row['local_datetime'])}</td>"
            f"<td>{html.escape(row['punch_type'])}</td>"
            f"<td>{html.escape(row['verify_mode'])}</td>"
            f"<td><code>{html.escape(row['external_uid'])}</code></td>"
            "</tr>"
            for row in rows
        )
        next_link = (
            f'<a class="button" href="/demo?after_id={rows[-1]["id"]}">Next 50 punches</a>'
            if has_more and rows
            else "<span class=\"muted\">End of data</span>"
        )
        previous_link = '<a class="button secondary" href="/demo?after_id=0">First page</a>' if after_id else ""
        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>ZKTeco mock attendance data</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#18212f;background:#f7f8fa}}
main{{max-width:1100px;margin:auto;background:#fff;padding:2rem;border-radius:12px;box-shadow:0 2px 12px #0001}}
h1{{margin-top:0}} .summary{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}}
.card{{background:#edf5ff;padding:.75rem 1rem;border-radius:8px}} table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{padding:.6rem;border-bottom:1px solid #e5e7eb;text-align:left;white-space:nowrap}} th{{background:#f1f5f9}}
code{{font-size:.8rem}} .actions{{display:flex;gap:.75rem;margin-top:1rem}} .button{{background:#146cce;color:white;padding:.55rem .8rem;border-radius:6px;text-decoration:none}}
.secondary{{background:#667085}} .muted{{color:#667085}}
</style></head><body><main>
<h1>ZKTeco mock attendance data</h1>
<p>Local development simulator — seed month <strong>{html.escape(metadata.get('seed_month', 'unknown'))}</strong>.</p>
<div class="summary"><div class="card"><strong>9</strong> mapped employees</div><div class="card"><strong>{total}</strong> punches</div><div class="card"><strong>50</strong> shown per page</div></div>
<table><thead><tr><th>ID</th><th>Device user</th><th>Local timestamp</th><th>Type</th><th>Verification</th><th>External UID</th></tr></thead>
<tbody>{row_html}</tbody></table><div class="actions">{previous_link}{next_link}</div>
</main></body></html>"""
        self.send_html(HTTPStatus.OK, page)

    def get_devices(self) -> None:
        with closing(self.db_connection()) as connection:
            rows = dict_rows(connection.execute("SELECT * FROM devices ORDER BY id"))
        for row in rows:
            row["active"] = bool(row["active"])
        self.send_json(HTTPStatus.OK, {"data": rows, "count": len(rows)})

    def get_employees(self) -> None:
        with closing(self.db_connection()) as connection:
            rows = dict_rows(
                connection.execute(
                    "SELECT device_user_id, name, email, department, active FROM employees ORDER BY device_user_id"
                )
            )
        for row in rows:
            row["active"] = bool(row["active"])
        self.send_json(HTTPStatus.OK, {"data": rows, "count": len(rows)})

    def get_punches(self, query: dict[str, list[str]]) -> None:
        def first(name: str, default: str | None = None) -> str | None:
            values = query.get(name)
            return values[0] if values else default

        after_id = int(first("after_id", "0") or 0)
        limit = int(first("limit", "100") or 100)
        if after_id < 0:
            raise ValueError("after_id must be zero or greater")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        conditions = ["id > ?"]
        parameters: list[Any] = [after_id]
        for parameter_name, column, operator in (
            ("from", "punch_datetime_utc", ">="),
            ("to", "punch_datetime_utc", "<"),
            ("device_user_id", "device_user_id", "="),
        ):
            value = first(parameter_name)
            if value:
                conditions.append(f"{column} {operator} ?")
                parameters.append(value)

        where_clause = " AND ".join(conditions)
        with closing(self.db_connection()) as connection:
            rows = dict_rows(
                connection.execute(
                    f"""
                    SELECT id, external_uid, device_serial, device_user_id,
                           punch_datetime_utc, local_datetime, punch_type,
                           verify_mode, work_code
                      FROM punches
                     WHERE {where_clause}
                     ORDER BY id
                     LIMIT ?
                    """,
                    parameters + [limit + 1],
                )
            )

        has_more = len(rows) > limit
        rows = rows[:limit]
        next_after_id = rows[-1]["id"] if rows else after_id
        self.send_json(
            HTTPStatus.OK,
            {
                "data": rows,
                "pagination": {
                    "after_id": after_id,
                    "next_after_id": next_after_id,
                    "limit": limit,
                    "returned": len(rows),
                    "has_more": has_more,
                },
            },
        )

    def get_stats(self) -> None:
        with closing(self.db_connection()) as connection:
            metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
            counts = {
                "devices": connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
                "employees": connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0],
                "punches": connection.execute("SELECT COUNT(*) FROM punches").fetchone()[0],
                "check_ins": connection.execute("SELECT COUNT(*) FROM punches WHERE punch_type = 'check_in'").fetchone()[0],
                "check_outs": connection.execute("SELECT COUNT(*) FROM punches WHERE punch_type = 'check_out'").fetchone()[0],
            }
        self.send_json(HTTPStatus.OK, {"seed": metadata, "counts": counts})


def create_server(host: str, port: int, db_path: str, api_key: str) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), ZKTecoMockHandler)
    server.config = {"db_path": db_path, "api_key": api_key}  # type: ignore[attr-defined]
    return server


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("ZKTECO_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ZKTECO_PORT", "8090")))
    parser.add_argument("--db", default=os.getenv("ZKTECO_DB_PATH", DEFAULT_DB_PATH))
    parser.add_argument("--month", default=os.getenv("ZKTECO_SEED_MONTH", DEFAULT_SEED_MONTH))
    parser.add_argument("--api-key", default=os.getenv("ZKTECO_API_KEY", DEFAULT_API_KEY))
    parser.add_argument("--reset-db", action="store_true")
    parser.add_argument("--init-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    initialize_database(args.db, args.month, reset=args.reset_db)
    if args.init_only:
        print(f"Initialized {args.db} with deterministic data for {args.month}")
        return

    server = create_server(args.host, args.port, args.db, args.api_key)
    print(f"ZKTeco mock API listening on http://{args.host}:{args.port}")
    print(f"Seed month: {args.month}; database: {args.db}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
