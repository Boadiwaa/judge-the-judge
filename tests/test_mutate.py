import pytest

from jtj.mutate import apply_mutation, apply_mutations
from jtj.schema import Mutation, ReferenceNote, risk_tier

NOTE = ReferenceNote(
    presenting_complaint="Left ankle injury 2 hours ago.",
    history="Fell down stairs. No head injury.",
    medications_allergies="No regular medications. Allergic to penicillin (rash).",
    examination="Tender over the left lateral malleolus.",
    impression="Possible fracture.",
    plan="X-ray. Paracetamol 1 g four times daily.",
    safety_netting="Return if foot becomes cold.",
)


def m(**kw):
    base = dict(error_id="x", type="LATERALITY", section="examination", evidence_turns=[1],
                seeded_severity=2, seeded_likelihood=2, seeded_rationale="r", subtle=False)
    base.update(kw)
    return Mutation(**base)


def test_substitution():
    out = apply_mutation(NOTE.examination, m(original_text="left", mutated_text="right"))
    assert out == "Tender over the right lateral malleolus."


def test_omission_tidies_whitespace():
    mu = m(section="medications_allergies", type="OMIT_SAFETY",
           original_text=" Allergic to penicillin (rash).", mutated_text="")
    assert apply_mutations(NOTE, [mu])["medications_allergies"] == "No regular medications."


def test_omission_mid_sentence():
    mu = m(section="plan", type="OMIT_OTHER", original_text=" four times daily", mutated_text="")
    assert apply_mutations(NOTE, [mu])["plan"] == "X-ray. Paracetamol 1 g."


def test_non_unique_original_rejected():
    with pytest.raises(ValueError):
        apply_mutation("left and left", m(original_text="left", mutated_text="right"))


def test_multiple_mutations_untouched_sections_preserved():
    out = apply_mutations(NOTE, [m(original_text="left", mutated_text="right"),
                                 m(section="plan", type="DOSE_UNIT", original_text="1 g", mutated_text="10 g")])
    assert out["examination"].startswith("Tender over the right")
    assert "10 g" in out["plan"]
    assert out["history"] == NOTE.history


@pytest.mark.parametrize("score,tier", [(1, "Low"), (4, "Low"), (5, "Moderate"), (9, "Moderate"),
                                        (10, "High"), (15, "High"), (16, "Very high"), (25, "Very high")])
def test_tiers(score, tier):
    assert risk_tier(score) == tier
