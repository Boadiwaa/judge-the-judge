"""Apply seeded mutations to a reference note to produce note variants (BUILD_SPEC §2.3)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import SECTIONS, Case, Mutation, ReferenceNote

DATA = Path(__file__).resolve().parents[2] / "data"


def _tidy(text: str) -> str:
    """Clean up after an omission: doubled spaces, space before punctuation, empty sentences."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"([.;])\s*[.;]", r"\1", text)
    text = re.sub(r",\s*\.", ".", text)
    return text.strip()


def apply_mutation(section_text: str, m: Mutation) -> str:
    count = section_text.count(m.original_text)
    if count != 1:
        raise ValueError(f"{m.error_id}: original_text found {count} times in {m.section}")
    out = section_text.replace(m.original_text, m.mutated_text, 1)
    return _tidy(out) if m.is_omission else out


def apply_mutations(note: ReferenceNote, mutations: list[Mutation]) -> dict[str, str]:
    sections = {s: note.section(s) for s in SECTIONS}
    for m in mutations:
        # Validate against the untouched reference text so mutation order cannot matter
        if note.section(m.section).count(m.original_text) != 1:
            raise ValueError(f"{m.error_id}: original_text not unique in reference {m.section}")
        sections[m.section] = apply_mutation(sections[m.section], m)
    return sections


def build_variant_notes(case: Case) -> dict[str, dict[str, str]]:
    return {v.variant_id: apply_mutations(case.reference_note, v.mutations) for v in case.variants}


def load_cases(cases_dir: Path | None = None) -> list[Case]:
    d = cases_dir or DATA / "cases"
    return [Case.model_validate_json(p.read_text()) for p in sorted(d.glob("case_*.json"))]


def note_to_text(sections: dict[str, str]) -> str:
    from .schema import SECTION_LABELS

    return "\n\n".join(f"{SECTION_LABELS[s].upper()}\n{sections[s]}" for s in SECTIONS)


def write_notes(cases: list[Case], out_dir: Path | None = None) -> int:
    out = out_dir or DATA / "notes"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in cases:
        for vid, sections in build_variant_notes(c).items():
            (out / f"{vid}.json").write_text(
                json.dumps({"variant_id": vid, "case_id": c.case_id, "sections": sections}, indent=2)
            )
            n += 1
    return n
