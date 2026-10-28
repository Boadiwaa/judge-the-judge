"""Case validation rules (BUILD_SPEC §5.2). Returns a list of problems; empty = valid."""
from __future__ import annotations

from collections import Counter

from .mutate import apply_mutations
from .schema import ERROR_TYPES, SETTINGS, Case

MIN_PER_TYPE = 8


def validate_case(c: Case) -> list[str]:
    p = []
    turns = {t.turn for t in c.transcript}
    if [t.turn for t in c.transcript] != list(range(1, len(c.transcript) + 1)):
        p.append(f"{c.case_id}: turns not numbered 1..N")
    if not 40 <= len(c.transcript) <= 90:
        p.append(f"{c.case_id}: {len(c.transcript)} turns (want 40-90)")
    kinds = sorted(v.kind for v in c.variants)
    if kinds != ["a", "b", "clean"]:
        p.append(f"{c.case_id}: variants {kinds}, want clean/a/b")
    for v in c.variants:
        if not v.variant_id.startswith(c.case_id + "_"):
            p.append(f"{v.variant_id}: id does not start with case id")
        if v.kind == "clean" and v.mutations:
            p.append(f"{v.variant_id}: clean variant has mutations")
        if v.kind != "clean" and not 2 <= len(v.mutations) <= 4:
            p.append(f"{v.variant_id}: {len(v.mutations)} mutations (want 2-4)")
        for m in v.mutations:
            sec = c.reference_note.section(m.section)
            n = sec.count(m.original_text)
            if n != 1:
                p.append(f"{m.error_id}: original_text appears {n}x in {m.section}: {m.original_text!r}")
            if m.original_text == m.mutated_text:
                p.append(f"{m.error_id}: mutation is a no-op")
            if m.type in ("OMIT_SAFETY", "OMIT_OTHER") and m.mutated_text:
                p.append(f"{m.error_id}: omission type but mutated_text not empty")
            if m.mutated_text == "" and m.type not in ("OMIT_SAFETY", "OMIT_OTHER", "CORRECTION_LOST", "PLAN_CHANGE"):
                p.append(f"{m.error_id}: empty mutated_text for type {m.type}")
            missing = [t for t in m.evidence_turns if t not in turns]
            if missing:
                p.append(f"{m.error_id}: evidence_turns {missing} not in transcript")
            if not m.error_id.startswith(v.variant_id + "_e"):
                p.append(f"{m.error_id}: id does not match variant")
        # mutations within a variant must not overlap each other
        if not p or all(v.variant_id not in x for x in p):
            try:
                apply_mutations(c.reference_note, v.mutations)
                origs = [(m.section, m.original_text) for m in v.mutations]
                for i, (s1, o1) in enumerate(origs):
                    for s2, o2 in origs[i + 1:]:
                        if s1 == s2 and (o1 in o2 or o2 in o1):
                            p.append(f"{v.variant_id}: overlapping mutations {o1!r} / {o2!r}")
            except ValueError as e:
                p.append(str(e))
    return p


def validate_dataset(cases: list[Case]) -> tuple[list[str], Counter]:
    p = [x for c in cases for x in validate_case(c)]
    ids = [c.case_id for c in cases]
    if len(set(ids)) != len(ids):
        p.append("duplicate case ids")
    eids = [m.error_id for c in cases for v in c.variants for m in v.mutations]
    if len(set(eids)) != len(eids):
        p.append("duplicate error ids")
    counts = Counter(m.type for c in cases for v in c.variants for m in v.mutations)
    return p, counts


def dataset_targets(cases: list[Case], counts: Counter) -> list[str]:
    """Full-dataset targets; only enforced once all 24 cases exist."""
    p = []
    for t in ERROR_TYPES:
        if counts[t] < MIN_PER_TYPE:
            p.append(f"type {t}: {counts[t]} < {MIN_PER_TYPE}")
    by_setting = Counter(c.setting for c in cases)
    for s in SETTINGS:
        if by_setting[s] != 4:
            p.append(f"setting {s}: {by_setting[s]} cases (want 4)")
    if sum(c.has_correction for c in cases) < 6:
        p.append(f"only {sum(c.has_correction for c in cases)} cases with a said-then-corrected moment (want ≥6)")
    return p
