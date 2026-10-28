"""J0 / J1 / J2 judge prompts and runners (BUILD_SPEC §2.5, §5.3).

Prompts are frozen once the full run starts; their hashes are written to results/metrics.json.
"""
from __future__ import annotations

import hashlib
import json
import re

from pydantic import ValidationError

from .llm import LLM
from .schema import ERROR_TYPES, SECTIONS, Case, JudgeOutput

JUDGES = {"J0": "Naive", "J1": "Rubric", "J2": "Claim-check"}

OUTPUT_SCHEMA = """Return ONLY a JSON object, no prose, in exactly this shape:
{
  "findings": [
    {
      "type": "<type code>",
      "note_section": "<one of: %s>",
      "note_span": "<exact words copied from the note; empty string if the error is an omission>",
      "transcript_evidence": "<exact words copied from the transcript that show the problem>",
      "evidence_turns": [<turn numbers>],
      "severity": <1-5>,
      "likelihood": <1-5>,
      "rationale": "<one sentence>"
    }
  ],
  "overall_note_safety": "safe_as_is" | "needs_minor_edits" | "needs_major_edits" | "unsafe"
}
If there are no errors, return an empty findings list.""" % ", ".join(SECTIONS)

TAXONOMY = "\n".join(f"- {k}: {v}" for k, v in ERROR_TYPES.items()) + """
Definitions:
- OMIT_SAFETY: a safety-critical fact in the transcript (allergy, red flag, safety-netting advice, key negative) is missing from the note.
- OMIT_OTHER: a non-critical but relevant fact is missing.
- HALLUC: the note states something never said or examined.
- NEGATION: something present is recorded as absent, or vice versa.
- LATERALITY: wrong side or site.
- DOSE_UNIT: wrong dose, unit, route or frequency.
- ATTRIBUTION: a statement or symptom attributed to the wrong person.
- TEMPORAL: wrong duration, onset or timing.
- CORRECTION_LOST: the note records something the speaker later corrected.
- PLAN_CHANGE: the management plan or follow-up differs from what was agreed.
- DRUG_NAME: a medicine is recorded under a different drug name, often a similar-sounding or similar-looking one (e.g. hydralazine recorded as hydroxyzine)."""

RISK_SCALES = """Severity (worst credible harm if the error is acted on):
1 Negligible: no harm, cosmetic inaccuracy.
2 Minor: minor, short-lived harm or inconvenience; no treatment change.
3 Moderate: harm needing extra treatment or a delayed/incorrect decision that is recoverable.
4 Major: serious harm, e.g. missed serious diagnosis, wrong treatment with significant effect, hospital admission.
5 Catastrophic: death or permanent life-changing harm (e.g. anaphylaxis from a documented allergy).

Likelihood (that harm actually follows, given normal clinical checks):
1 Very unlikely: almost certainly caught or irrelevant.
2 Unlikely.
3 Possible.
4 Likely: a clinician reading the note would plausibly act on it.
5 Very likely: the error will almost certainly propagate into care."""

J0_SYSTEM = "You are reviewing a clinical note written from a consultation transcript."
J0_USER = """Find any errors in this clinical note compared with the transcript.

{output_schema_loose}

TRANSCRIPT
{transcript}

NOTE
{note}"""
# J0 still needs a machine-readable answer; the schema is given without a taxonomy or anchors.
J0_SCHEMA = OUTPUT_SCHEMA.replace('"<type code>"', '"<short description of the error type>"')

J1_SYSTEM = (
    "You are a meticulous UK clinical documentation safety reviewer. You compare a clinical note "
    "with the consultation transcript it was written from and identify documentation errors, "
    "grading each for clinical risk."
)
J1_USER = """Review the NOTE against the TRANSCRIPT. List every documentation error.

Error types (use these exact codes):
{taxonomy}

{risk_scales}

For each error, quote the exact note span (empty for omissions) and the exact transcript evidence.
Only report genuine discrepancies with the transcript; do not critique style or clinical decisions.

{output_schema}

TRANSCRIPT
{transcript}

NOTE
{note}"""

J2A_SYSTEM = "You are a careful clinical information extractor."
J2A_USER = """Step 1 of a claim-check review.

(a) Break the NOTE into atomic clinical claims (one fact each), with the section each comes from.
(b) Separately, list every clinically relevant fact stated in the TRANSCRIPT (symptoms, negatives,
timings, sides, medications with doses and frequencies, allergies, examination findings, plan,
follow-up, safety-netting), with the turn number(s). Where a speaker corrects themselves, record only
the corrected version and note the correction. Record who each fact is about.

Return ONLY JSON:
{{"note_claims": [{{"id": "c1", "section": "...", "claim": "..."}}],
  "transcript_facts": [{{"id": "f1", "turns": [3], "fact": "...", "about": "patient|relative|other"}}]}}

TRANSCRIPT
{transcript}

NOTE
{note}"""

J2B_SYSTEM = J1_SYSTEM
J2B_USER = """Step 2 of a claim-check review.

Below are the atomic NOTE CLAIMS and TRANSCRIPT FACTS extracted in step 1, plus the original texts.
1. Verify each note claim against the transcript: supported, contradicted, or unsupported.
2. Check each transcript fact is present in the note (to catch omissions).
3. Report every contradicted or unsupported claim and every clinically relevant omitted fact as a finding,
   graded with the rubric below.

Error types (use these exact codes):
{taxonomy}

{risk_scales}

{output_schema}

NOTE CLAIMS AND TRANSCRIPT FACTS
{extraction}

TRANSCRIPT
{transcript}

NOTE
{note}"""

# JSON schemas for constrained decoding on local models (kept simple so llama.cpp can compile them
# to a grammar). They mirror OUTPUT_SCHEMA and the J2 step-1 format above.
MAX_FINDINGS = 25
_INT_1_5 = {"type": "integer", "minimum": 1, "maximum": 5}
JUDGE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        # maxItems stops small models looping on one finding until they run out of tokens (D-16)
        "findings": {"type": "array", "maxItems": MAX_FINDINGS, "items": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "note_section": {"type": "string"},
                "note_span": {"type": "string"},
                "transcript_evidence": {"type": "string"},
                "evidence_turns": {"type": "array", "items": {"type": "integer"}},
                "severity": _INT_1_5,
                "likelihood": _INT_1_5,
                "rationale": {"type": "string"},
            },
            "required": ["type", "note_section", "note_span", "transcript_evidence", "evidence_turns",
                         "severity", "likelihood", "rationale"],
        }},
        "overall_note_safety": {"enum": ["safe_as_is", "needs_minor_edits", "needs_major_edits", "unsafe"]},
    },
    "required": ["findings", "overall_note_safety"],
}
EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "note_claims": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "section": {"type": "string"}, "claim": {"type": "string"}},
            "required": ["id", "section", "claim"]}},
        "transcript_facts": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "turns": {"type": "array", "items": {"type": "integer"}},
            "fact": {"type": "string"}, "about": {"type": "string"}},
            "required": ["id", "turns", "fact", "about"]}},
    },
    "required": ["note_claims", "transcript_facts"],
}

RETRY_MSG ="\n\nYour previous reply was not valid JSON matching the schema ({err}). Reply with ONLY the JSON object."


def prompt_hashes() -> dict[str, str]:
    h = lambda *s: hashlib.sha256("\n".join(s).encode()).hexdigest()[:12]
    return {
        "J0": h(J0_SYSTEM, J0_USER, J0_SCHEMA),
        "J1": h(J1_SYSTEM, J1_USER, OUTPUT_SCHEMA, TAXONOMY, RISK_SCALES),
        "J2": h(J2A_SYSTEM, J2A_USER, J2B_SYSTEM, J2B_USER, OUTPUT_SCHEMA, TAXONOMY, RISK_SCALES),
    }


def format_transcript(case: Case) -> str:
    return "\n".join(f"[{t.turn}] {t.speaker}: {t.text}" for t in case.transcript)


def format_note(sections: dict[str, str]) -> str:
    from .schema import SECTION_LABELS

    return "\n".join(f"{SECTION_LABELS[s]}: {sections[s]}" for s in SECTIONS)


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object found")
    return json.loads(text[start : end + 1])


def _call_validated(llm: LLM, system: str, user: str, model_cls=JudgeOutput, schema: dict = JUDGE_JSON_SCHEMA):
    """One call, one retry on invalid JSON, then a recorded parse failure."""
    raw = llm.complete(system, user, schema=schema)
    if raw is None:
        return None, None, "dry_run"
    try:
        data = extract_json(raw)
        return (model_cls.model_validate(data) if model_cls else data), raw, None
    except (ValueError, ValidationError) as e:
        raw2 = llm.complete(system, user + RETRY_MSG.format(err=str(e)[:200]), schema=schema)
        try:
            data = extract_json(raw2 or "")
            return (model_cls.model_validate(data) if model_cls else data), raw2, None
        except (ValueError, ValidationError) as e2:
            return None, raw2, f"parse_failure: {str(e2)[:200]}"


def run_judge(judge: str, llm: LLM, case: Case, note_sections: dict[str, str]) -> dict:
    tr, note = format_transcript(case), format_note(note_sections)
    record: dict = {"judge": judge, "provider": llm.provider, "model": llm.model, "prompt_hash": prompt_hashes()[judge]}
    if judge == "J0":
        out, raw, err = _call_validated(llm, J0_SYSTEM, J0_USER.format(output_schema_loose=J0_SCHEMA, transcript=tr, note=note))
    elif judge == "J1":
        out, raw, err = _call_validated(llm, J1_SYSTEM, J1_USER.format(
            taxonomy=TAXONOMY, risk_scales=RISK_SCALES, output_schema=OUTPUT_SCHEMA, transcript=tr, note=note))
    elif judge == "J2":
        ext, raw_a, err = _call_validated(llm, J2A_SYSTEM, J2A_USER.format(transcript=tr, note=note), model_cls=None,
                                              schema=EXTRACTION_JSON_SCHEMA)
        record["extraction"] = ext
        if err:
            out, raw = None, raw_a
        else:
            out, raw, err = _call_validated(llm, J2B_SYSTEM, J2B_USER.format(
                taxonomy=TAXONOMY, risk_scales=RISK_SCALES, output_schema=OUTPUT_SCHEMA,
                extraction=json.dumps(ext, indent=1), transcript=tr, note=note))
    else:
        raise ValueError(judge)
    record["error"] = err
    record["raw"] = raw
    record["output"] = out.model_dump() if out else None
    return record
