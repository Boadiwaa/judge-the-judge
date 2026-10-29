"""Anonymous usage counts (SQLite at env USAGE_DB, default next to the ratings database).

Stores what was viewed and challenge scores, keyed by a random per-visit id that lives only in server
memory. No cookies, IP addresses, user agents or anything typed by visitors (rater mode input is never
logged here). Timestamps are kept to the minute. Logging must never break the app, so every write
swallows its own errors.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .rating_status import db_path as ratings_db_path

log = logging.getLogger("jtj.app.usage")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,          -- UTC, to the minute
    visit TEXT NOT NULL,       -- random per-visit id; '-' for static-file hits outside a visit
    event TEXT NOT NULL,       -- visit | page | challenge | download
    route TEXT,
    detail TEXT,
    phone INTEGER              -- 1 if the window was narrow (phone layout) at the time
);
"""
EVENTS = ("visit", "page", "challenge", "download")


def db_path() -> Path:
    return Path(os.environ.get("USAGE_DB") or ratings_db_path().with_name("usage.sqlite"))


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.executescript(SCHEMA)
    return con


def new_visit() -> str:
    return uuid.uuid4().hex[:12]


def log_event(visit: str, event: str, route: str | None = None, detail: str | None = None,
              phone: bool | None = None) -> None:
    """Record one event. Never raises."""
    if event not in EVENTS:
        return
    at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    try:
        con = connect()
        with con:
            con.execute("INSERT INTO events (at, visit, event, route, detail, phone) VALUES (?, ?, ?, ?, ?, ?)",
                        (at, visit, event, (route or "")[:200] or None, (detail or "")[:100] or None,
                         None if phone is None else int(phone)))
        con.close()
    except (sqlite3.Error, OSError):
        log.warning("usage logging failed", exc_info=True)


def summary() -> str:
    """Plain-text overview for the owner export."""
    con = connect()
    with con:
        q = lambda sql: con.execute(sql).fetchall()  # noqa: E731
        visits, phone = q("SELECT COUNT(*), COALESCE(SUM(phone), 0) FROM events WHERE event = 'visit'")[0]
        days = q("SELECT substr(at, 1, 10), COUNT(*) FROM events WHERE event = 'visit' GROUP BY 1 ORDER BY 1")
        pages = q("SELECT CASE WHEN instr(route, '?') THEN substr(route, 1, instr(route, '?') - 1) ELSE route END "
                  "AS r, COUNT(*), COUNT(DISTINCT visit) FROM events WHERE event = 'page' GROUP BY r ORDER BY 3 DESC")
        ch = q("SELECT detail FROM events WHERE event = 'challenge'")
        dl = q("SELECT COUNT(*) FROM events WHERE event = 'download'")[0][0]
    con.close()
    caught = total = 0
    for (d,) in ch:
        try:
            a, b = (int(x) for x in d.split(" ")[0].split("/"))
        except (AttributeError, ValueError):
            continue
        caught, total = caught + a, total + b
    lines = [f"Usage summary, generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", "",
             f"Visits: {visits} ({phone} on a phone-width screen)", "", "Visits per day:"]
    lines += [f"  {d}: {n}" for d, n in days] or ["  none"]
    lines += ["", "Pages (views, visits that saw it):"]
    lines += [f"  {r or '/'}: {n}, {v}" for r, n, v in pages] or ["  none"]
    lines += ["", f"Challenges revealed: {len(ch)}"]
    if total:
        lines.append(f"Planted errors caught by visitors: {caught}/{total} ({caught / total:.0%})")
    lines += [f"Protocol downloads: {dl}", ""]
    return "\n".join(lines)


def export_zip() -> bytes:
    """events.csv plus summary.txt in one zip (for the owner)."""
    import csv
    import io
    import zipfile

    buf = io.BytesIO()
    con = connect()
    with con, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        cur = con.execute("SELECT * FROM events ORDER BY id")
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow([d[0] for d in cur.description])
        w.writerows(cur.fetchall())
        z.writestr("events.csv", out.getvalue())
        z.writestr("summary.txt", summary())
    con.close()
    return buf.getvalue()
