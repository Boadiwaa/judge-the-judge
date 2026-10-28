"""Rater mode: storage, page states, agreement computation and the owner export. All data here is a
temporary test database; nothing touches data/ratings.sqlite."""
import base64
import io
import sqlite3
import zipfile

import pytest

from jtj.agreement import compute
from jtj.app import rating_status as R
from jtj.app.data import AppData, load
from jtj.app.main import PAGES


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("RATINGS_DB", str(tmp_path / "r.sqlite"))
    monkeypatch.setenv("RATER_CODE", "test-code")
    return tmp_path / "r.sqlite"


@pytest.fixture(scope="module")
def data():
    d = load()
    return AppData(cases=d.cases, notes=d.notes, summary=d.summary)


def _catch_all_spans(data, vid):
    """Spans a perfect rater would mark: the sentence holding each change, or 'missing' for omissions."""
    from jtj.app.data import sentences

    c, v = data.variant(vid)
    out = []
    for m in v.mutations:
        if m.is_omission:
            out.append({"section": m.section, "start": -1, "end": -1, "text": "[missing]", "type": m.type,
                        "severity": m.seeded_severity, "likelihood": m.seeded_likelihood})
            continue
        sp = next(s for s in data.spans(vid, m.section) if s.mutation.error_id == m.error_id)
        a, b = next((a, b) for a, b in sentences(data.notes[vid][m.section]) if a < sp.end and b > sp.start)
        out.append({"section": m.section, "start": a, "end": b, "text": "x", "type": m.type,
                    "severity": m.seeded_severity, "likelihood": m.seeded_likelihood})
    return out


def test_store_round_trip(db, data):
    rid = R.get_or_create_rater("AB", "GP")
    assert R.get_or_create_rater("AB", "GP") == rid
    R.save_note(rid, "case_07_a", "needs_major_edits", "c", _catch_all_spans(data, "case_07_a"))
    R.save_note(rid, "case_07_a", "unsafe", "", [])  # re-rating replaces
    assert R.rated_variants(rid) == {"case_07_a"}
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM span_ratings").fetchone()[0] == 0
    assert con.execute("SELECT overall FROM note_ratings").fetchone()[0] == "unsafe"
    R.save_adjudication(rid, "J1:case_07_a:0", "yes")
    assert R.adjudicated_flags(rid) == {"J1:case_07_a:0"}
    z = zipfile.ZipFile(io.BytesIO(R.export_zip()))
    assert sorted(z.namelist()) == ["adjudications.csv", "note_ratings.csv", "raters.csv", "span_ratings.csv"]
    assert R.rater_progress() == [("AB (GP)", 1)]


def test_agreement_locked_then_unlocked(db, data):
    vids = sorted(data.notes)[:20]
    r1 = R.get_or_create_rater("P1", "GP")
    r2 = R.get_or_create_rater("P2", "ED")
    for v in vids[:10]:
        R.save_note(r1, v, "unsafe", "", _catch_all_spans(data, v))
    assert compute(R.connect(), data.cases, data, {}, [])["unlocked"] is False
    for v in vids[10:]:
        R.save_note(r1, v, "unsafe", "", _catch_all_spans(data, v))
    for v in vids:
        R.save_note(r2, v, "safe_as_is", "", [])  # rater 2 finds nothing
    res = compute(R.connect(), data.cases, data, {}, [])
    assert res["unlocked"] is True
    n_err = sum(len(data.variant(v)[1].mutations) for v in vids)
    cs = res["clinician_sensitivity"]
    assert (cs["k"], cs["n"]) == (n_err, 2 * n_err)  # rater 1 caught every one, rater 2 none


def test_rate_page_states(db, data, monkeypatch):
    from test_app import make_ctx

    ctx = make_ctx(data)
    assert PAGES["/rate"](ctx) is not None  # signed out, code set
    ctx.state["rater"] = {"id": R.get_or_create_rater("ZZ", "GP"), "initials": "ZZ"}
    assert PAGES["/rate"](ctx) is not None  # rating the first note
    ctx.query = {"tab": "flags"}
    assert PAGES["/rate"](ctx) is not None  # no flags yet
    monkeypatch.delenv("RATER_CODE")
    assert PAGES["/rate"](make_ctx(data)) is not None  # disabled


def test_rater_order_is_seeded_per_rater():
    from jtj.app.pages.rate import _order

    items = [f"v{i}" for i in range(30)]
    assert _order(1, items) == _order(1, items) and _order(1, items) != _order(2, items)


def test_export_requires_owner_code(db, monkeypatch):
    from starlette.testclient import TestClient

    from jtj.app.main import asgi_app

    client = TestClient(asgi_app())
    assert client.get("/export/ratings.zip").status_code == 404  # OWNER_CODE unset
    monkeypatch.setenv("OWNER_CODE", "s3cret")
    assert client.get("/export/ratings.zip").status_code == 401
    bad = base64.b64encode(b"owner:wrong").decode()
    assert client.get("/export/ratings.zip", headers={"Authorization": f"Basic {bad}"}).status_code == 401
    good = base64.b64encode(b"owner:s3cret").decode()
    r = client.get("/export/ratings.zip", headers={"Authorization": f"Basic {good}"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
