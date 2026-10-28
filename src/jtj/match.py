"""Deterministic matching of judge findings to seeded errors (BUILD_SPEC §2.6). No LLM."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .schema import Finding, Mutation

THRESHOLD = 80
MIN_LEN = 4  # spans shorter than this are too ambiguous to match on (e.g. "a", "OD")


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^\w\s'/.%-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def overlaps(a: str, b: str, threshold: int = THRESHOLD) -> bool:
    a, b = norm(a), norm(b)
    if len(a) < MIN_LEN or len(b) < MIN_LEN:
        return False
    return fuzz.partial_ratio(a, b) >= threshold


def finding_matches(f: Finding, m: Mutation, turn_text: dict[int, str] | None = None) -> bool:
    """turn_text (turn number -> transcript text) enables the omission extension: a judge quoting the
    transcript turns that prove the omitted fact also counts. Pass None for the spec-literal rule."""
    if m.is_omission:
        # Omission: the judge must point at the missing content, usually via transcript evidence.
        # A note_span quoting the omitted text also counts.
        if any(overlaps(x, m.original_text) for x in (f.transcript_evidence, f.note_span) if x):
            return True
        if turn_text and f.transcript_evidence:
            return any(overlaps(f.transcript_evidence, turn_text[t]) for t in m.evidence_turns if t in turn_text)
        return False
    return bool(f.note_span) and overlaps(f.note_span, m.mutated_text)


@dataclass
class NoteMatch:
    detected: dict[str, int | None] = field(default_factory=dict)  # error_id -> finding index or None
    unmatched: list[int] = field(default_factory=list)  # finding indices matching no seeded error
    type_agree: dict[str, bool] = field(default_factory=dict)


def match_note(
    findings: list[Finding], mutations: list[Mutation], turn_text: dict[int, str] | None = None
) -> NoteMatch:
    """Each seeded error is detected if any finding matches it. A finding may match more than one
    seeded error (e.g. adjacent mutations); type agreement is recorded but not required."""
    res = NoteMatch()
    used: set[int] = set()
    for m in mutations:
        hit = next((i for i, f in enumerate(findings) if finding_matches(f, m, turn_text)), None)
        res.detected[m.error_id] = hit
        if hit is not None:
            used.add(hit)
            res.type_agree[m.error_id] = findings[hit].type == m.type
    res.unmatched = [i for i in range(len(findings)) if i not in used]
    return res
