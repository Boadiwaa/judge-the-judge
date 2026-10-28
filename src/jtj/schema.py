"""Pydantic models for cases, mutations and judge output (BUILD_SPEC §5.1, §5.3)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ERROR_TYPES: dict[str, str] = {
    "OMIT_SAFETY": "Safety fact omitted",
    "OMIT_OTHER": "Other fact omitted",
    "HALLUC": "Hallucinated finding",
    "NEGATION": "Negation flip",
    "LATERALITY": "Wrong side / site",
    "DOSE_UNIT": "Dose / unit / frequency",
    "ATTRIBUTION": "Wrong speaker",
    "TEMPORAL": "Timing",
    "CORRECTION_LOST": "Self-correction lost",
    "PLAN_CHANGE": "Plan altered",
}
JUDGE_TYPES = set(ERROR_TYPES) | {"UNSPECIFIED"}

SECTIONS = [
    "presenting_complaint",
    "history",
    "medications_allergies",
    "examination",
    "impression",
    "plan",
    "safety_netting",
]
SECTION_LABELS = {
    "presenting_complaint": "Presenting complaint",
    "history": "History",
    "medications_allergies": "Medications and allergies",
    "examination": "Examination",
    "impression": "Impression",
    "plan": "Plan",
    "safety_netting": "Safety-netting",
}

SETTINGS = ["GP_ADULT", "GP_PAEDS", "ED", "MENTAL_HEALTH", "OUTPATIENT", "REMOTE"]
SETTING_LABELS = {
    "GP_ADULT": "GP (adult)",
    "GP_PAEDS": "GP (paediatrics)",
    "ED": "ED",
    "MENTAL_HEALTH": "Mental health",
    "OUTPATIENT": "Outpatient",
    "REMOTE": "Telephone / remote",
}

TIERS = ["Low", "Moderate", "High", "Very high"]

Speaker = Literal["Clinician", "Patient", "Relative"]
Section = Literal[
    "presenting_complaint",
    "history",
    "medications_allergies",
    "examination",
    "impression",
    "plan",
    "safety_netting",
]
OverallSafety = Literal["safe_as_is", "needs_minor_edits", "needs_major_edits", "unsafe"]


def risk_tier(score: int) -> str:
    """Map severity × likelihood (1–25) to a tier (BUILD_SPEC §2.4)."""
    if not 1 <= score <= 25:
        raise ValueError(f"risk score out of range: {score}")
    if score <= 4:
        return "Low"
    if score <= 9:
        return "Moderate"
    if score <= 15:
        return "High"
    return "Very high"


class Turn(BaseModel):
    turn: int
    speaker: Speaker
    text: str


class ReferenceNote(BaseModel):
    presenting_complaint: str
    history: str
    medications_allergies: str
    examination: str
    impression: str
    plan: str
    safety_netting: str

    def section(self, name: str) -> str:
        return getattr(self, name)


class Mutation(BaseModel):
    error_id: str
    type: str
    section: Section
    original_text: str = Field(min_length=1)
    mutated_text: str = ""
    evidence_turns: list[int] = Field(min_length=1)
    seeded_severity: int = Field(ge=1, le=5)
    seeded_likelihood: int = Field(ge=1, le=5)
    seeded_rationale: str = Field(min_length=1)
    description: str = ""  # plain-English one-liner for the UI, e.g. "Penicillin allergy dropped"

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in ERROR_TYPES:
            raise ValueError(f"unknown error type {v}")
        return v

    @property
    def is_omission(self) -> bool:
        return self.mutated_text == ""

    @property
    def risk_score(self) -> int:
        return self.seeded_severity * self.seeded_likelihood

    @property
    def tier(self) -> str:
        return risk_tier(self.risk_score)


class Variant(BaseModel):
    variant_id: str
    mutations: list[Mutation] = []

    @property
    def kind(self) -> str:
        return self.variant_id.rsplit("_", 1)[-1]  # clean | a | b


class Case(BaseModel):
    case_id: str
    setting: str
    title: str
    clinician_reviewed: bool = False
    has_correction: bool = False  # something is said and later corrected in the transcript
    transcript: list[Turn]
    reference_note: ReferenceNote
    variants: list[Variant]

    @field_validator("setting")
    @classmethod
    def _known_setting(cls, v: str) -> str:
        if v not in SETTINGS:
            raise ValueError(f"unknown setting {v}")
        return v


# ---------------- judge output ----------------


class Finding(BaseModel):
    type: str = "UNSPECIFIED"
    note_section: str = ""
    note_span: str = ""
    transcript_evidence: str = ""
    evidence_turns: list[int] = []
    severity: int | None = Field(default=None, ge=1, le=5)
    likelihood: int | None = Field(default=None, ge=1, le=5)
    rationale: str = ""

    @field_validator("type", mode="before")
    @classmethod
    def _map_type(cls, v):
        # J0 has no taxonomy: free-text types collapse to UNSPECIFIED (BUILD_SPEC §5.3)
        v = str(v or "").strip().upper()
        return v if v in JUDGE_TYPES else "UNSPECIFIED"


class JudgeOutput(BaseModel):
    findings: list[Finding] = []
    overall_note_safety: OverallSafety | None = None
