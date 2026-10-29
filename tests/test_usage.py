"""Anonymous usage logging: writes to its own database, never raises, and exports a summary."""
import io
import zipfile

from jtj.app import usage


def test_log_summary_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_DB", str(tmp_path / "usage.sqlite"))
    v = usage.new_visit()
    usage.log_event(v, "visit", phone=True)
    usage.log_event(v, "page", route="/explorer?case=case_07&mode=challenge", phone=True)
    usage.log_event(v, "page", route="/scorecard", phone=True)
    usage.log_event(v, "challenge", route="case_07_a", detail="2/3 caught, 1 other marks")
    usage.log_event("-", "download", route="/protocol.md")
    usage.log_event(v, "not-an-event")  # ignored
    s = usage.summary()
    assert "Visits: 1 (1 on a phone-width screen)" in s
    assert "/explorer: 1, 1" in s and "/scorecard: 1, 1" in s
    assert "Planted errors caught by visitors: 2/3 (67%)" in s and "Protocol downloads: 1" in s
    z = zipfile.ZipFile(io.BytesIO(usage.export_zip()))
    assert set(z.namelist()) == {"events.csv", "summary.txt"}
    rows = z.read("events.csv").decode().strip().splitlines()
    assert len(rows) == 6 and rows[0] == "id,at,visit,event,route,detail,phone"


def test_logging_failure_never_raises(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    monkeypatch.setenv("USAGE_DB", str(blocker / "usage.sqlite"))
    usage.log_event("x", "visit")  # parent is a file, so the write fails; must not raise
