"""Protocol document generated from the code and data, so the page and the download never drift.

Used by the Protocol page and written to app/assets/protocol.md at server start (BUILD_SPEC §3.3.5).
"""
from __future__ import annotations

from collections import Counter

from . import judges, stats
from .llm import DEFAULT_MODELS, SEED
from .match import MIN_LEN, THRESHOLD
from .schema import ERROR_TYPES, SETTING_LABELS, TIERS, Case

VERSION = "0.1 (draft for clinician review)"
DATE = "2026-10-28"

TYPE_EXAMPLES = {
    "OMIT_SAFETY": "Allergy, red flag or safety-netting advice dropped",
    "OMIT_OTHER": "Social history detail dropped",
    "HALLUC": "\"Chest clear\" when no chest exam was discussed",
    "NEGATION": "\"Denies chest pain\" becomes \"reports chest pain\"",
    "LATERALITY": "Left knee becomes right knee",
    "DOSE_UNIT": "5 mg becomes 50 mg; BD becomes OD",
    "ATTRIBUTION": "Mother's symptom recorded as the child's",
    "TEMPORAL": "\"3 days\" becomes \"3 weeks\"",
    "CORRECTION_LOST": "Note keeps the figure the patient later corrected",
    "PLAN_CHANGE": "Follow-up \"1 week\" becomes \"if needed\"",
}


def judge_prompts() -> dict[str, list[tuple[str, str]]]:
    """(label, text) pairs per judge, exactly as sent (with placeholders for transcript and note)."""
    fill = dict(taxonomy=judges.TAXONOMY, risk_scales=judges.RISK_SCALES, output_schema=judges.OUTPUT_SCHEMA,
                output_schema_loose=judges.J0_SCHEMA, transcript="{transcript}", note="{note}",
                extraction="{step 1 output}")
    return {
        "J0": [("System", judges.J0_SYSTEM), ("User", judges.J0_USER.format(**fill))],
        "J1": [("System", judges.J1_SYSTEM), ("User", judges.J1_USER.format(**fill))],
        "J2": [("Step 1 system", judges.J2A_SYSTEM), ("Step 1 user", judges.J2A_USER.format(**fill)),
               ("Step 2 system", judges.J2B_SYSTEM), ("Step 2 user", judges.J2B_USER.format(**fill))],
    }


def sections(cases: list[Case]) -> list[tuple[str, str]]:
    errs = [m for c in cases for v in c.variants for m in v.mutations]
    n_high = sum(m.tier in ("High", "Very high") for m in errs)
    _, lo, hi = stats.wilson(round(0.8 * n_high), n_high)
    half = (hi - lo) / 2
    n_conf = stats.n_for_halfwidth(0.8, 0.05)
    by_setting = Counter(c.setting for c in cases)
    by_type = Counter(m.type for m in errs)
    by_tier = Counter(m.tier for m in errs)
    hashes = judges.prompt_hashes()

    out: list[tuple[str, str]] = []
    out.append(("Background", (
        "Ambient AI scribes turn a consultation into a clinical note. At scale nobody can read every note, so "
        "safety claims depend on automated judges, usually large language models, that find documentation errors "
        "and grade their clinical risk. If the judge is wrong, every safety number built on it is wrong. Word-level "
        "metrics such as word error rate are poor proxies for clinical harm; what matters is the clinical risk of "
        "each error. A judge's agreement with clinicians must be measured, not assumed. Earlier work found that "
        "LLMs rated their own first-aid answers 10–19% higher than clinicians did. This study asks: who checks the "
        "checker?")))
    out.append(("Questions", (
        "**Primary:** How well does an LLM judge detect clinically important errors in AI-generated notes, and does "
        "a more structured judge design detect more high-risk errors than a naive one?\n\n"
        "**Secondary:** Does the judge grade clinical risk the way the answer key (and, later, clinicians) would? "
        "Which error types do judges miss most?")))
    out.append(("Design", (
        "Synthetic UK consultations, each with a transcript and a clean reference note fully supported by the "
        "transcript. \"AI-style\" note variants are created by programmatically injecting known errors (seeded "
        "errors), giving an exact answer key. Three judge designs are run over every note; each seeded error is "
        "scored detected or missed by a deterministic matcher. Judge findings that match no seeded error are "
        "*unadjudicated flags*, sent for clinician review rather than counted as false positives. Clinicians later "
        "rate notes blind, which unlocks agreement statistics.")))
    setting_rows = "\n".join(f"| {SETTING_LABELS[s]} | {by_setting[s]} |" for s in SETTING_LABELS)
    out.append(("Cases", (
        f"{len(cases)} consultations across 6 settings, each with one clean variant and two seeded variants of 2–4 "
        f"errors: {sum(len(c.variants) for c in cases)} notes and {len(errs)} seeded errors. "
        f"{sum(c.has_correction for c in cases)} cases contain something said and later corrected. All content is "
        "synthetic, uses fictional names, follows UK practice (NICE, BNF) and is drafted for clinician review.\n\n"
        "| Setting | Cases |\n| --- | --- |\n" + setting_rows)))
    type_rows = "\n".join(f"| `{t}` | {ERROR_TYPES[t]} | {TYPE_EXAMPLES[t]} | {by_type[t]} |" for t in ERROR_TYPES)
    out.append(("Error taxonomy", "| Code | Type | Example | n |\n| --- | --- | --- | --- |\n" + type_rows))
    tier_rows = "\n".join(f"| {r} | {t} | {by_tier[t]} |" for r, t in zip(("1–4", "5–9", "10–15", "16–25"), TIERS))
    out.append(("Risk grading (answer key)", (
        "Every seeded error has a severity (1–5) and likelihood of harm (1–5) with a one-sentence clinical rationale, "
        "in the style of UK digital clinical safety risk management (DCB0129/DCB0160, ISO 14971). Risk score = "
        "severity × likelihood.\n\n| Score | Tier | Seeded errors |\n| --- | --- | --- |\n" + tier_rows +
        "\n\nThe grades are drafts and are flagged `clinician_reviewed: false` until reviewed.")))
    out.append(("Judges", (
        "All judges see the transcript and the note and return strict JSON.\n\n"
        "- **J0 Naive:** \"Find any errors in this clinical note compared with the transcript.\" No rubric or "
        "taxonomy; free-text types are mapped to `UNSPECIFIED`.\n"
        "- **J1 Rubric:** given the taxonomy and anchored severity and likelihood scales; asked for type, quoted "
        "note span, quoted transcript evidence, severity, likelihood and rationale.\n"
        "- **J2 Claim-check:** two steps. (a) Extract atomic claims from the note and clinically relevant facts "
        "from the transcript. (b) Verify each claim (supported / contradicted / unsupported) and check each fact "
        "is present in the note, then grade findings with the J1 rubric.\n\n"
        f"**Model:** {DEFAULT_MODELS['local']} (Gemma 4 E2B instruct, 4-bit GGUF), an open-weight model run "
        f"locally with llama.cpp. Temperature 0, fixed seed {SEED}, output constrained to the JSON schema, at most "
        f"{judges.MAX_FINDINGS} findings per note, one retry on invalid JSON then recorded as a parse failure "
        "(its seeded errors count as missed). The web app never calls a model; all outputs are precomputed.\n\n"
        f"**Prompt hashes (frozen at the full run):** J0 `{hashes['J0']}`, J1 `{hashes['J1']}`, J2 `{hashes['J2']}`. "
        "Full prompts are below.")))
    out.append(("Matching rule", (
        "Deterministic, no LLM. A judge finding matches a seeded error in the same note if its quoted note span "
        f"overlaps the mutated text (rapidfuzz partial ratio ≥ {THRESHOLD} after lower-casing and normalising "
        "whitespace and punctuation). For omissions, the finding matches if its quoted transcript evidence or note "
        "span overlaps the omitted original text, **or** its transcript evidence overlaps one of the transcript "
        "turns that prove the omitted fact (amendment D-03, approved before any judge run). Spans shorter than "
        f"{MIN_LEN} characters never match. Type agreement is recorded but not required. Each seeded error is "
        "detected or missed per judge; the spec-literal rule is reported as a sensitivity analysis.")))
    out.append(("Endpoints", (
        "**Primary:** sensitivity of each judge for seeded errors in the High and Very high tiers, with Wilson 95% "
        "confidence intervals.\n\n**Secondary:**\n"
        "- Sensitivity by error type and by tier, per judge.\n"
        "- Paired comparisons J2 vs J0 and J1 vs J0 on the same seeded errors: McNemar's exact test, Holm "
        "correction across the two comparisons (high-risk errors; all errors reported too).\n"
        "- Severity agreement between judge and answer key on detected errors: quadratic-weighted Cohen's kappa "
        "and Gwet's AC2 (ordinal weights), with case-level cluster bootstrap 95% CIs (2,000 resamples, fixed "
        f"seed {stats.BOOTSTRAP_SEED}).\n"
        "- Unadjudicated flags per clean note, per judge.\n"
        "- Once clinician ratings exist (at least 2 raters × 20 notes): clinician vs judge agreement on error "
        "presence (Gwet's AC1) and risk tier (AC2); inter-clinician agreement; precision of judge flags after "
        "adjudication.")))
    out.append(("Sample size", (
        f"There are {n_high} High or Very high risk seeded errors. At a sensitivity near 0.80, the 95% CI half-width "
        f"is about ±{half:.2f}. This is a **pilot that estimates precision, not a confirmatory study**. A "
        f"confirmatory study would need about **{n_conf} high-risk errors** for a half-width of ±0.05 "
        "(normal approximation, p = 0.80).")))
    out.append(("Reporting checklist (GRRAS / DECIDE-AI spirit)", "\n".join([
        "- [x] Raters/judges and subjects described (models, prompts, settings; synthetic cases)",
        "- [x] Rating scales defined with anchors (severity, likelihood, tiers)",
        "- [x] Answer key construction described (seeded mutations, rationale per error)",
        "- [x] Sample size justified, and its limits stated",
        "- [x] Statistical methods named, with uncertainty (Wilson, McNemar exact + Holm, κ, AC1/AC2, bootstrap)",
        "- [x] AI system described: model, version, decoding, prompts and hashes, failure handling",
        "- [x] Matching rule fixed before analysis; amendments recorded and dated",
        "- [ ] Clinician review of cases and answer key (pending)",
        "- [ ] Inter-rater reliability among clinicians (pending ratings)",
        "- [ ] Human factors: how judge output would be used in practice (out of scope for this pilot)",
    ])))
    out.append(("Limitations", "\n".join([
        "- Synthetic consultations and programmatically seeded errors may be easier or harder than real scribe errors.",
        "- Pilot sample: confidence intervals are wide; differences between judges may not be detectable.",
        "- The answer-key risk grades were drafted by one author and await clinician review.",
        "- One small open-weight judge model (about 2B effective parameters) run on a laptop; results may not "
        "generalise to larger or hosted models.",
        "- Unadjudicated flags are not yet classified, so judge precision is unknown.",
        "- The matcher relies on judges quoting text; a correct finding with a poor quote may be scored as a miss.",
    ])))
    out.append(("Version", f"Version {VERSION}, {DATE}. Independent study; synthetic data only; not a medical device."))
    return out


def markdown(cases: list[Case]) -> str:
    md = ["# Judge the Judge: protocol", ""]
    for title, body in sections(cases):
        md += [f"## {title}", "", body, ""]
    md += ["## Appendix: judge prompts", ""]
    for j, parts in judge_prompts().items():
        for label, text in parts:
            md += [f"### {j} · {label}", "", "```text", text, "```", ""]
    return "\n".join(md)
