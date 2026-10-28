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
    "DRUG_NAME": "\"hydralazine\" becomes \"hydroxyzine\"",
}

EXTERNAL_VALIDITY_TITLE = "External validity: why seeded errors"
EXTERNAL_VALIDITY = """Planted errors cannot tell us how often a judge misses errors in real notes. They measure something \
studies of real notes cannot: **an exact miss rate for known error types**, because the answer key is complete. \
A study of real notes can only count errors that someone flagged, and expert reviewers miss errors too, so the true \
number of errors is unknown and the miss rate has to be estimated statistically.

**What planted errors give:**

1. **A floor test.** Like spike-and-recovery in a laboratory assay, or a phantom in radiology quality assurance: \
if a judge misses a planted tenfold dose error, it will miss subtler real ones. Passing is necessary, not sufficient.
2. **The miss rate, exactly,** by error type and risk tier.
3. **Fair comparisons.** Identical notes that differ by one change isolate the effect of judge design, model or prompt.
4. **Cheap, repeatable regression testing.** Re-run in minutes when a model or prompt changes, with no clinician \
time. In production this becomes a standing check that a judge update has not started missing, for example, \
drug-name errors: post-market surveillance for the judge itself.
5. **No patient data,** so it can run from day one.

**What they don't give:**

- Planted errors may be easier than, or simply different from, the errors a real scribe makes, so sensitivity \
here is likely an *upper bound* on real-world sensitivity for the same error types.
- Error types that were not planted are not measured at all.
- Modelling planted errors on reported real-world failure modes (drug-name confusions, negation flips) reduces \
this problem but does not solve it.

**Recommended design:** use seeded errors *alongside* real-note validation (blinded clinician review, adjudicated \
reference standards, and latent-class or capture–recapture estimates of the errors everyone missed), not instead \
of it. In production, real failures found in surveillance become new seeded cases, so the test set keeps up with \
the errors that actually occur."""


# Each reference was checked against its publisher or arXiv record on 2026-10-28.
REFERENCES = [
    "Zheng L, Chiang W-L, et al. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS 2023 "
    "(Datasets and Benchmarks). [arXiv:2306.05685](https://arxiv.org/abs/2306.05685)",
    "Wang P, et al. Large Language Models are not Fair Evaluators. ACL 2024, pp. 9440–9450. "
    "[aclanthology.org/2024.acl-long.511](https://aclanthology.org/2024.acl-long.511)",
    "Panickssery A, Bowman SR, Feng S. LLM Evaluators Recognize and Favor Their Own Generations. NeurIPS 2024. "
    "[arXiv:2404.13076](https://arxiv.org/abs/2404.13076)",
    "Liu Y, Iter D, Xu Y, Wang S, Xu R, Zhu C. G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment. "
    "EMNLP 2023, pp. 2511–2522. [doi:10.18653/v1/2023.emnlp-main.153](https://aclanthology.org/2023.emnlp-main.153)",
    "Kim S, et al. Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models. "
    "EMNLP 2024. [aclanthology.org/2024.emnlp-main.248](https://aclanthology.org/2024.emnlp-main.248)",
    "Min S, Krishna K, Lyu X, Lewis M, Yih W, Koh PW, Iyyer M, Zettlemoyer L, Hajishirzi H. FActScore: Fine-grained "
    "Atomic Evaluation of Factual Precision in Long Form Text Generation. EMNLP 2023, pp. 12076–12100. "
    "[doi:10.18653/v1/2023.emnlp-main.741](https://aclanthology.org/2023.emnlp-main.741)",
    "Wei J, et al. Long-form factuality in large language models. NeurIPS 2024. "
    "[arXiv:2403.18802](https://arxiv.org/abs/2403.18802)",
    "Dhuliawala S, et al. Chain-of-Verification Reduces Hallucination in Large Language Models. Findings of ACL 2024, "
    "pp. 3563–3578. [arXiv:2309.11495](https://arxiv.org/abs/2309.11495)",
    "Kryściński W, McCann B, Xiong C, Socher R. Evaluating the Factual Consistency of Abstractive Text Summarization. "
    "EMNLP 2020, pp. 9332–9346. [doi:10.18653/v1/2020.emnlp-main.750](https://aclanthology.org/2020.emnlp-main.750)",
    "Ben Abacha A, et al. MEDEC: A Benchmark for Medical Error Detection and Correction in Clinical Notes. Findings of "
    "ACL 2025, pp. 22539–22550. [arXiv:2412.19260](https://arxiv.org/abs/2412.19260)",
    "Asgari E, et al. A framework to assess clinical safety and hallucination rates of LLMs for medical text "
    "summarisation. npj Digital Medicine 2025;8:274. "
    "[doi:10.1038/s41746-025-01670-7](https://doi.org/10.1038/s41746-025-01670-7)",
    "Verga P, et al. Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models. "
    "arXiv preprint 2024. [arXiv:2404.18796](https://arxiv.org/abs/2404.18796)",
    "Gu J, et al. A Survey on LLM-as-a-Judge. arXiv preprint 2024 (revised 2025). "
    "[arXiv:2411.15594](https://arxiv.org/abs/2411.15594)",
]

RELATED_WORK = (
    "**LLMs as judges.** Using a strong LLM to grade other models' output became mainstream with MT-Bench, where GPT-4 "
    "agreed with human preferences over 80% of the time [1]. The same work, and later studies, documented systematic "
    "biases: position bias, where reordering candidates can flip the verdict [2]; verbosity bias [1]; and "
    "self-preference, where evaluators recognise and favour their own outputs [3]. These findings are why a judge's "
    "agreement with clinicians has to be measured rather than assumed. A recent survey covers both how to make "
    "judges more reliable and how to evaluate their reliability [13].\n\n"
    "**Where each judge design comes from.** J0 is the plain LLM-as-a-judge baseline [1]. J1 follows rubric-based "
    "evaluation: G-Eval gives the judge criteria and a form to fill in [4], and Prometheus 2 trains open evaluators "
    "to score against user-defined rubrics [5]. Its severity × likelihood scale comes from UK clinical safety "
    "risk management (DCB0129/DCB0160) rather than the NLP literature. J2 follows atomic-fact verification: FActScore "
    "splits text into atomic facts and checks each against a source [6], SAFE automates this with search [7], and "
    "Chain-of-Verification has a model plan and answer its own verification questions [8]. Those methods mainly "
    "measure precision; J2 also checks every transcript fact for presence in the note, to catch omissions.\n\n"
    "**Seeded errors and clinical notes.** Creating evaluation data by applying rule-based edits (entity swaps, "
    "negation, number changes) to source text goes back to FactCC [9]. MEDEC, a public benchmark for detecting and "
    "correcting medical errors in clinical notes (five error types, 3,848 texts), found that recent LLMs were still "
    "outperformed by doctors [10]. A clinical-safety framework for LLM note generation graded clinician-annotated "
    "hallucinations and omissions for harm [11]; this study's risk tiers follow the same spirit.\n\n"
    "**How this design relates to current practice.** J1 and J2 are well-established designs, not the frontier. "
    "The judge here is a small open-weight model run locally. Current directions include strong reasoning models as "
    "judges, juries of diverse models (a panel of three smaller models from different families beat a single large "
    "judge at lower cost [12]), judges fine-tuned on clinician labels, and calibrated judges that abstain. This "
    "study's contribution is the validation method (planted errors with an exact answer key, clinical risk grading, "
    "blinded clinician ratings and honest uncertainty), which can be applied unchanged to any of those judges."
)


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
    out.append(("Related work", RELATED_WORK))
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
    n_subtle = sum(m.subtle for m in errs)
    out.append(("Error taxonomy", "| Code | Type | Example | n |\n| --- | --- | --- | --- |\n" + type_rows + (
        "\n\nThe dataset is weighted towards drug-name confusions and negation flips, reported as the commonest "
        "serious errors made by production ambient scribes: at least 12 of each. Drug-name errors swap a drug the "
        "reference note mentions for a look-alike or sound-alike (for example amlodipine recorded as amiloride), "
        "and the rationale records why the swap is dangerous.\n\n"
        f"Each seeded error is also tagged **subtle** or **obvious**. {n_subtle} of {len(errs)} "
        f"({n_subtle / len(errs):.0%}) are subtle: the note still reads as plausible and internally consistent, so "
        "a busy clinician could miss it on a quick read and it can only be caught by checking the transcript (for "
        "example \"3 days\" recorded as \"3 weeks\", or a figure the patient corrected). Obvious errors make the "
        "note look wrong on its own: an implausible dose, or a statement that contradicts another part of the "
        "note. Sensitivity is reported separately for each.")))
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
        "- Sensitivity by error type, by tier, and for subtle vs obvious errors, per judge.\n"
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
    out.append((EXTERNAL_VALIDITY_TITLE, EXTERNAL_VALIDITY))
    out.append(("Reporting checklist (GRRAS / DECIDE-AI spirit)", "\n".join([
        "- [x] Raters/judges and subjects described (models, prompts, settings; synthetic cases)",
        "- [x] Rating scales defined with anchors (severity, likelihood, tiers)",
        "- [x] Answer key construction described (seeded mutations, rationale per error, subtle/obvious tag)",
        "- [x] External validity of the reference standard discussed (seeded vs real-note errors)",
        "- [x] Sample size justified, and its limits stated",
        "- [x] Statistical methods named, with uncertainty (Wilson, McNemar exact + Holm, κ, AC1/AC2, bootstrap)",
        "- [x] AI system described: model, version, decoding, prompts and hashes, failure handling",
        "- [x] Matching rule fixed before analysis; amendments recorded and dated",
        "- [ ] Clinician review of cases and answer key (pending)",
        "- [ ] Inter-rater reliability among clinicians (pending ratings)",
        "- [ ] Human factors: how judge output would be used in practice (out of scope for this pilot)",
    ])))
    out.append(("Limitations", "\n".join([
        "- Synthetic consultations and programmatically seeded errors may be easier than, or different from, real "
        "scribe errors, so sensitivity here is likely an upper bound; error types not planted are not measured "
        "(see External validity).",
        "- Pilot sample: confidence intervals are wide; differences between judges may not be detectable.",
        "- The answer-key risk grades were drafted by one author and await clinician review.",
        "- One small open-weight judge model (about 2B effective parameters) run on a laptop; results may not "
        "generalise to larger or hosted models.",
        "- Unadjudicated flags are not yet classified, so judge precision is unknown.",
        "- The matcher relies on judges quoting text; a correct finding with a poor quote may be scored as a miss.",
    ])))
    out.append(("References", "\n".join(f"{i}. {r}" for i, r in enumerate(REFERENCES, 1))))
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
