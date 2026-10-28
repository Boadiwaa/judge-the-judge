"""Read-only view of the clinician ratings database (SQLite at env RATINGS_DB; BUILD_SPEC §3.2).

The schema is created by rater mode; here we only count progress, and an absent or unreadable
database simply means "no ratings yet".
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from ..mutate import DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS raters (
    rater_id INTEGER PRIMARY KEY AUTOINCREMENT,
    initials TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (initials, role)
);
CREATE TABLE IF NOT EXISTS note_ratings (
    rater_id INTEGER NOT NULL REFERENCES raters(rater_id),
    variant_id TEXT NOT NULL,
    overall TEXT NOT NULL CHECK (overall IN ('safe_as_is','needs_minor_edits','needs_major_edits','unsafe')),
    comment TEXT,
    rated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (rater_id, variant_id)
);
CREATE TABLE IF NOT EXISTS span_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_id INTEGER NOT NULL REFERENCES raters(rater_id),
    variant_id TEXT NOT NULL,
    section TEXT NOT NULL,
    start_pos INTEGER NOT NULL,  -- character offsets in the section; -1/-1 = "something missing here"
    end_pos INTEGER NOT NULL,
    span_text TEXT NOT NULL,
    error_type TEXT NOT NULL,
    severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    likelihood INTEGER NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
    comment TEXT,
    rated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS adjudications (
    rater_id INTEGER NOT NULL REFERENCES raters(rater_id),
    flag_id TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('yes','no','unsure')),
    comment TEXT,
    rated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (rater_id, flag_id)
);
"""


def db_path() -> Path:
    return Path(os.environ.get("RATINGS_DB") or DATA / "ratings.sqlite")


def connect(create: bool = False) -> sqlite3.Connection | None:
    p = db_path()
    if not p.exists() and not create:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.executescript(SCHEMA)
    return con


def rater_progress() -> list[tuple[str, int]]:
    """[(rater label, notes rated)] sorted by most notes rated. Never raises."""
    try:
        con = connect()
        if con is None:
            return []
        with con:
            rows = con.execute(
                "SELECT r.initials || ' (' || r.role || ')', COUNT(n.variant_id) FROM raters r "
                "LEFT JOIN note_ratings n USING (rater_id) GROUP BY r.rater_id ORDER BY 2 DESC").fetchall()
        return [(who, n) for who, n in rows]
    except sqlite3.Error:
        return []


# ---------------- writes (rater mode) ----------------


def get_or_create_rater(initials: str, role: str) -> int:
    con = connect(create=True)
    with con:
        con.execute("INSERT OR IGNORE INTO raters (initials, role) VALUES (?, ?)", (initials, role))
        return con.execute("SELECT rater_id FROM raters WHERE initials = ? AND role = ?",
                           (initials, role)).fetchone()[0]


def rated_variants(rater_id: int) -> set[str]:
    con = connect()
    if con is None:
        return set()
    with con:
        return {r[0] for r in con.execute("SELECT variant_id FROM note_ratings WHERE rater_id = ?", (rater_id,))}


def save_note(rater_id: int, variant_id: str, overall: str, comment: str, spans: list[dict]) -> None:
    """Replace this rater's rating of one note (note-level rating plus marked spans) atomically."""
    con = connect(create=True)
    with con:
        con.execute("DELETE FROM span_ratings WHERE rater_id = ? AND variant_id = ?", (rater_id, variant_id))
        con.execute("INSERT OR REPLACE INTO note_ratings (rater_id, variant_id, overall, comment) VALUES (?, ?, ?, ?)",
                    (rater_id, variant_id, overall, comment or None))
        con.executemany(
            "INSERT INTO span_ratings (rater_id, variant_id, section, start_pos, end_pos, span_text, error_type, "
            "severity, likelihood, comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(rater_id, variant_id, s["section"], s["start"], s["end"], s["text"], s["type"], s["severity"],
              s["likelihood"], s.get("comment") or None) for s in spans])


def adjudicated_flags(rater_id: int) -> set[str]:
    con = connect()
    if con is None:
        return set()
    with con:
        return {r[0] for r in con.execute("SELECT flag_id FROM adjudications WHERE rater_id = ?", (rater_id,))}


def save_adjudication(rater_id: int, flag_id: str, verdict: str, comment: str = "") -> None:
    con = connect(create=True)
    with con:
        con.execute("INSERT OR REPLACE INTO adjudications (rater_id, flag_id, verdict, comment) VALUES (?, ?, ?, ?)",
                    (rater_id, flag_id, verdict, comment or None))


def export_zip() -> bytes:
    """All tables as CSV files in one zip (for the owner)."""
    import csv
    import io
    import zipfile

    buf = io.BytesIO()
    con = connect(create=True)
    with con, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for table in ("raters", "note_ratings", "span_ratings", "adjudications"):
            cur = con.execute(f"SELECT * FROM {table}")  # noqa: S608 (fixed table names)
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow([d[0] for d in cur.description])
            w.writerows(cur.fetchall())
            z.writestr(f"{table}.csv", out.getvalue())
    return buf.getvalue()
