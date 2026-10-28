"""End-to-end metrics on a tiny fixture with known answers (separate from real data)."""
import json

import pytest

from jtj.metrics import compute_all
from jtj.schema import Case

NOTE = {
    "presenting_complaint": "Left knee pain for 3 days.",
    "history": "Twisted knee playing football. Denies locking.",
    "medications_allergies": "No regular medications. Allergic to penicillin (rash).",
    "examination": "Effusion of the left knee.",
    "impression": "Soft tissue knee injury.",
    "plan": "Ibuprofen 400 mg three times daily with food. Review in 1 week.",
    "safety_netting": "Return if unable to weight-bear.",
}
TRANSCRIPT = [{"turn": i, "speaker": "Patient" if i % 2 else "Clinician", "text": t} for i, t in enumerate([
    "", "My left knee, three days now.", "Any locking?", "No locking.", "Allergies?", "Penicillin, I get a rash.",
], start=0)][1:]


def mut(eid, typ, sec, orig, new, sev, lik, turns=(1,)):
    return {"error_id": eid, "type": typ, "section": sec, "original_text": orig, "mutated_text": new,
            "evidence_turns": list(turns), "seeded_severity": sev, "seeded_likelihood": lik, "seeded_rationale": "r"}


def make_case(cid):
    return Case.model_validate({
        "case_id": cid, "setting": "GP_ADULT", "title": "Knee", "transcript": TRANSCRIPT, "reference_note": NOTE,
        "variants": [
            {"variant_id": f"{cid}_clean", "mutations": []},
            {"variant_id": f"{cid}_a", "mutations": [
                mut(f"{cid}_a_e1", "LATERALITY", "examination", "left knee", "right knee", 3, 4),          # High 12
                mut(f"{cid}_a_e2", "OMIT_SAFETY", "medications_allergies", " Allergic to penicillin (rash).", "", 5, 4, (4, 5)),  # VH 20
            ]},
            {"variant_id": f"{cid}_b", "mutations": [
                mut(f"{cid}_b_e1", "TEMPORAL", "presenting_complaint", "3 days", "3 weeks", 2, 2),  # Low 4
            ]},
        ]})


def write(d, judge, vid, findings):
    p = d / judge
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{vid}.json").write_text(json.dumps({"output": {"findings": findings, "overall_note_safety": None}}))


@pytest.fixture
def fixture(tmp_path):
    cases = [make_case("fx_01"), make_case("fx_02")]
    for cid in ("fx_01", "fx_02"):
        # J0: catches laterality only, one flag on clean note
        write(tmp_path, "J0", f"{cid}_clean", [{"note_span": "Soft tissue knee injury"}])
        write(tmp_path, "J0", f"{cid}_a", [{"note_span": "right knee", "severity": 3}])
        write(tmp_path, "J0", f"{cid}_b", [])
        # J2: catches everything
        write(tmp_path, "J2", f"{cid}_clean", [])
        write(tmp_path, "J2", f"{cid}_a", [
            {"type": "LATERALITY", "note_span": "Effusion of the right knee", "severity": 3},
            {"type": "OMIT_SAFETY", "transcript_evidence": "Penicillin, I get a rash.", "severity": 5}])
        write(tmp_path, "J2", f"{cid}_b", [{"type": "TEMPORAL", "note_span": "for 3 weeks", "severity": 2}])
    return cases, tmp_path


def test_end_to_end_known_answers(fixture):
    cases, d = fixture
    res = compute_all(cases, d, judges=("J0", "J1", "J2"), n_boot=50)
    m = res["metrics"]
    assert m["status"] == "partial" and m["judges_available"] == ["J0", "J2"]
    assert m["n_errors"] == 6 and m["n_high_errors"] == 4
    assert (m["per_judge"]["J0"]["primary"]["k"], m["per_judge"]["J0"]["primary"]["n"]) == (2, 4)
    assert m["per_judge"]["J2"]["primary"]["k"] == 4
    assert m["per_judge"]["J0"]["by_type"]["OMIT_SAFETY"]["k"] == 0
    assert m["per_judge"]["J0"]["clean_flags_per_note"]["mean"] == 1.0
    assert m["per_judge"]["J2"]["clean_flags_per_note"]["mean"] == 0.0
    j2v0 = next(c for c in m["comparisons"] if c["a"] == "J2" and c["scope"] == "high")
    assert (j2v0["only_a"], j2v0["only_b"]) == (2, 0)
    assert [x["error_id"] for x in m["most_dangerous_misses"]] == ["fx_01_a_e2", "fx_02_a_e2"]
    assert all(x["missed_by"] == ["J0"] for x in m["most_dangerous_misses"])
    assert len([f for f in res["flags"] if f["judge"] == "J0"]) == 2


def test_strict_matching_misses_verbatim_omission(fixture):
    cases, d = fixture
    m = compute_all(cases, d, judges=("J2",), strict_spec_matching=True, n_boot=10)["metrics"]
    assert m["per_judge"]["J2"]["by_type"]["OMIT_SAFETY"]["k"] == 0


def test_no_outputs_is_pending(tmp_path):
    m = compute_all([make_case("fx_01")], tmp_path)["metrics"]
    assert m["status"] == "pending" and m["per_judge"] == {}
