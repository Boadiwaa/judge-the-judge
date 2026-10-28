"""Hand-built matcher cases (BUILD_SPEC §2.6, §7: at least 10, incl. near-misses and omissions)."""
from jtj.match import match_note
from jtj.schema import Finding, Mutation


def mut(**kw) -> Mutation:
    base = dict(error_id="e1", type="LATERALITY", section="examination", evidence_turns=[1],
                seeded_severity=3, seeded_likelihood=3, seeded_rationale="r", subtle=False)
    base.update(kw)
    return Mutation(**base)


LAT = mut(original_text="left lateral malleolus", mutated_text="right lateral malleolus")
OMIT = mut(error_id="e2", type="OMIT_SAFETY", section="medications_allergies",
           original_text="Allergic to penicillin (rash).", mutated_text="")
DOSE = mut(error_id="e3", type="DOSE_UNIT", section="plan",
           original_text="paracetamol 1 g four times daily", mutated_text="paracetamol 1 g six times daily")


def detected(findings, muts=(LAT,)):
    return match_note([Finding(**f) for f in findings], list(muts))


def test_exact_span_detects():
    r = detected([{"note_span": "right lateral malleolus", "type": "LATERALITY"}])
    assert r.detected["e1"] == 0 and r.type_agree["e1"]


def test_span_with_extra_context_detects():
    r = detected([{"note_span": "Bony tenderness at the posterior edge of the right lateral malleolus."}])
    assert r.detected["e1"] == 0


def test_case_and_punctuation_insensitive():
    r = detected([{"note_span": "RIGHT  lateral-malleolus"}])
    assert r.detected["e1"] == 0


def test_type_disagreement_still_matches():
    r = detected([{"note_span": "right lateral malleolus", "type": "HALLUC"}])
    assert r.detected["e1"] == 0 and r.type_agree["e1"] is False


def test_unrelated_span_is_unmatched_flag():
    r = detected([{"note_span": "Neurovascularly intact distally"}])
    assert r.detected["e1"] is None and r.unmatched == [0]


def test_near_miss_different_sentence_not_matched():
    # Mentions "lateral" but quotes a different part of the note
    r = detected([{"note_span": "Swelling over the lateral aspect"}])
    assert r.detected["e1"] is None


def test_omission_matched_via_paraphrased_evidence():
    r = detected([{"transcript_evidence": "allergic to penicillin, rash"}], [OMIT])
    assert r.detected["e2"] == 0


def test_omission_verbatim_quote_needs_turn_extension():
    # Verbatim patient words score ~56 against the note-style original: spec-literal rule misses it,
    # the evidence-turn extension catches it (DECISIONS.md D-03).
    f = [Finding(transcript_evidence="Penicillin. I come out in a rash.", type="OMIT_SAFETY")]
    turns = {1: "Penicillin. I come out in a rash.", 2: "No, none of those."}
    assert match_note(f, [OMIT]).detected["e2"] is None
    assert match_note(f, [OMIT], turns).detected["e2"] == 0


def test_omission_extension_ignores_quotes_from_other_turns():
    f = [Finding(transcript_evidence="No, none of those.")]
    turns = {1: "Penicillin. I come out in a rash.", 2: "No, none of those."}
    assert match_note(f, [OMIT], turns).detected["e2"] is None


def test_omission_matched_via_note_span_quote():
    r = detected([{"note_span": "Allergic to penicillin (rash)", "transcript_evidence": ""}], [OMIT])
    assert r.detected["e2"] == 0


def test_omission_not_matched_by_generic_flag():
    r = detected([{"note_span": "No regular medications.", "transcript_evidence": "No regular meds"}], [OMIT])
    assert r.detected["e2"] is None


def test_dose_near_miss_original_value_not_matched_if_wrong_number():
    # Judge quotes a *different* drug line; should not match the dose mutation
    r = detected([{"note_span": "ibuprofen 400 mg three times daily"}], [DOSE])
    assert r.detected["e3"] is None


def test_dose_matched():
    r = detected([{"note_span": "1 g six times daily"}], [DOSE])
    assert r.detected["e3"] == 0


def test_tiny_span_ignored():
    r = detected([{"note_span": "OD"}], [DOSE])
    assert r.detected["e3"] is None


def test_one_finding_can_cover_two_adjacent_errors_and_extra_flag_counted():
    m2 = mut(error_id="e9", type="TEMPORAL", section="examination",
             original_text="2 hours", mutated_text="2 days ago at the right lateral malleolus")
    r = detected([{"note_span": "right lateral malleolus"}, {"note_span": "Plan reasonable overall"}], [LAT, m2])
    assert r.detected["e1"] == 0 and r.detected["e9"] == 0
    assert r.unmatched == [1]


def test_empty_findings_all_missed():
    r = detected([], [LAT, OMIT, DOSE])
    assert all(v is None for v in r.detected.values()) and r.unmatched == []
