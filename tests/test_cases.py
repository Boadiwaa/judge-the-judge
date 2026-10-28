"""Run case validation (BUILD_SPEC §5.2) over every real case file."""
import pytest

from jtj.mutate import load_cases
from jtj.validate import dataset_targets, validate_case, validate_dataset

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c.case_id for c in CASES])
def test_case_valid(case):
    assert validate_case(case) == []


def test_dataset_unique_ids():
    problems, _ = validate_dataset(CASES)
    assert not [p for p in problems if "duplicate" in p]


@pytest.mark.skipif(len(CASES) < 24, reason="dataset incomplete: full-dataset targets apply at 24 cases")
def test_dataset_targets():
    _, counts = validate_dataset(CASES)
    assert dataset_targets(CASES, counts) == []


def test_all_cases_marked_unreviewed_or_explicitly_reviewed():
    assert all(isinstance(c.clinician_reviewed, bool) for c in CASES)


# BUILD_SPEC §2.3 / §7: realistic weighting, drug-name swaps, subtle errors
ERRORS = [m for c in CASES for v in c.variants for m in v.mutations]


def test_drug_name_and_negation_each_have_at_least_12():
    for t in ("DRUG_NAME", "NEGATION"):
        assert sum(m.type == t for m in ERRORS) >= 12, t


def test_every_drug_name_error_swaps_a_reference_note_drug_for_a_different_one():
    from jtj.validate import drug_swap

    by_id = {c.case_id: c for c in CASES}
    for m in (m for m in ERRORS if m.type == "DRUG_NAME"):
        pair = drug_swap(m.original_text, m.mutated_text)
        assert pair and pair[0] != pair[1], m.error_id
        note = by_id[m.error_id[:7]].reference_note.section(m.section)
        assert pair[0].lower() in note.lower(), m.error_id  # the drug swapped out is in the reference note


def test_drug_swap_rejects_non_swaps():
    from jtj.validate import drug_swap

    assert drug_swap("Amlodipine 5 mg once daily.", "Amiloride 5 mg once daily.") == ("amlodipine", "amiloride")
    assert drug_swap("Amlodipine 5 mg once daily.", "Amlodipine 10 mg once daily.") is None  # dose change
    assert drug_swap("Amlodipine 5 mg.", "Amlodipine and amiloride 5 mg.") is None  # original drug still there
    assert drug_swap("Ramipril 5 mg.", "Lisinopril 5 mg.") is None  # not a listed look-alike pair


def test_at_least_a_third_of_errors_are_subtle():
    assert all(isinstance(m.subtle, bool) for m in ERRORS)
    assert sum(m.subtle for m in ERRORS) >= len(ERRORS) / 3
