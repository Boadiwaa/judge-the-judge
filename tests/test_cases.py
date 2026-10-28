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
