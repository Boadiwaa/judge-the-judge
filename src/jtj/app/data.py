"""Read-only data for the app: cases, note variants, answer key and (if present) results.

The app never calls an LLM (BUILD_SPEC §3.2). Results are only treated as headline-ready when
metrics.json says status == "complete"; a partial run is shown as pending on the Overview.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..metrics import answer_key_summary
from ..mutate import DATA, build_variant_notes, load_cases
from ..schema import ERROR_TYPES, SECTIONS, Case, Mutation, Variant

RESULTS_DIR = Path(os.environ.get("JTJ_RESULTS_DIR", DATA / "results"))

PLAIN_TYPE = {  # plain-English titles for the Explorer side panel
    "OMIT_SAFETY": "Safety-critical fact left out",
    "OMIT_OTHER": "Detail left out",
    "HALLUC": "Something recorded that never happened",
    "NEGATION": "Yes recorded as no (or no as yes)",
    "LATERALITY": "Wrong side or site",
    "DOSE_UNIT": "Wrong dose, unit or frequency",
    "ATTRIBUTION": "Someone else's information recorded as the patient's",
    "TEMPORAL": "Wrong timing",
    "CORRECTION_LOST": "Kept the figure the speaker corrected",
    "PLAN_CHANGE": "Plan changed from what was agreed",
}


@dataclass
class Span:
    """A highlighted region of a note section: a seeded error or an omission marker."""
    start: int
    end: int  # == start for an omission marker
    mutation: Mutation


@dataclass
class AppData:
    cases: list[Case]
    notes: dict[str, dict[str, str]]  # variant_id -> section -> text
    summary: dict
    metrics: dict | None = None
    matches: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    agreement: dict | None = None

    @property
    def status(self) -> str:
        return (self.metrics or {}).get("status", "pending")

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    @property
    def has_any_results(self) -> bool:
        return bool(self.metrics and self.metrics.get("per_judge"))

    @property
    def all_reviewed(self) -> bool:
        return self.summary["all_reviewed"]

    def case(self, case_id: str) -> Case:
        return next(c for c in self.cases if c.case_id == case_id)

    def variant(self, variant_id: str) -> tuple[Case, Variant]:
        c = self.case(variant_id.rsplit("_", 1)[0])
        return c, next(v for v in c.variants if v.variant_id == variant_id)

    def mutation(self, error_id: str) -> tuple[Case, Variant, Mutation]:
        c, v = self.variant(error_id.rsplit("_", 1)[0])
        return c, v, next(m for m in v.mutations if m.error_id == error_id)

    def verdict(self, judge: str, error_id: str) -> dict | None:
        """Matcher result for one judge and seeded error, or None if that note was not judged."""
        return self.matches.get(judge, {}).get(error_id)

    def flags_for(self, judge: str, variant_id: str) -> list[dict]:
        return [f for f in self.flags if f["judge"] == judge and f["variant_id"] == variant_id]

    def spans(self, variant_id: str, section: str) -> list[Span]:
        """Locate each seeded error inside the variant's section text."""
        c, v = self.variant(variant_id)
        text = self.notes[variant_id][section]
        ref = c.reference_note.section(section)
        out = []
        for m in v.mutations:
            if m.section != section:
                continue
            if not m.is_omission:
                i = text.find(m.mutated_text)
                if i >= 0:
                    out.append(Span(i, i + len(m.mutated_text), m))
                continue
            # omission: anchor on the reference text just before the removed span
            before = ref[: ref.find(m.original_text)].rstrip()
            ctx = before[-25:]
            i = text.find(ctx) + len(ctx) if ctx and text.find(ctx) >= 0 else (0 if not before else len(text))
            out.append(Span(i, i, m))
        return sorted(out, key=lambda s: s.start)


def _load_json(name: str):
    p = RESULTS_DIR / name
    return json.loads(p.read_text()) if p.exists() else None


@lru_cache(maxsize=1)
def load() -> AppData:
    cases = load_cases()
    notes = {}
    for c in cases:
        notes.update(build_variant_notes(c))
    d = AppData(cases=cases, notes=notes, summary=answer_key_summary(cases))
    try:
        d.metrics = _load_json("metrics.json")
        d.matches = _load_json("matches.json") or {}
        d.flags = _load_json("flags.json") or []
        d.agreement = _load_json("agreement.json")
    except (json.JSONDecodeError, OSError):
        d.metrics, d.matches, d.flags, d.agreement = None, {}, [], None  # never show a stack trace; fall back to pending
    return d


def sentences(text: str) -> list[tuple[int, int]]:
    """Sentence boundaries for challenge-mode clicking (split after . ; ? ! followed by space)."""
    out, start = [], 0
    for m in re.finditer(r"(?<=[.;?!])\s+", text):
        out.append((start, m.start()))
        start = m.end()
    if start < len(text):
        out.append((start, len(text)))
    return out


__all__ = ["AppData", "Span", "load", "sentences", "PLAIN_TYPE", "ERROR_TYPES", "SECTIONS"]
