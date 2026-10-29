# Morning report (2026-10-29)

**Judge the Judge** tests how well three LLM judge designs find errors I planted in AI-style consultation notes. The pipeline is complete: 24 synthetic UK consultations, 72 notes, 174 planted errors, three judges run on all 72 notes, final metrics computed, and the app and Docker image built and tested locally. **Nothing is deployed, and nothing is pushed** (there is no git remote).

Everything below is a **pilot on synthetic data with one small local model**. These results are not a claim about any product.

## 1. Status

| Phase | State |
| --- | --- |
| 1. Scaffold | Done |
| 2. Cases (24 cases, 174 errors, 11 types) | Done. All 24 cases clinician-reviewed (2026-10-29) |
| 3. Pipeline (mutate, judges, matcher, stats) | Done |
| 4. Judge run (J0, J1, J2 on 72 notes) | **Done** on the spec v2 prompts (D-25). The six cases edited during review (02, 03, 09, 10, 17, 21) were re-judged |
| 5. UI (Overview, Explorer, Scorecard, Protocol, About) | Done, showing final results |
| 6. Rater mode | Done. Needs `RATER_CODE` and raters |
| 7. Polish and deploy prep | Done. Docker image rebuilt and tested on 2026-10-29. Not deployed |
| 8. This report | Done |

There are 114 tests, and all pass.

## 2. Headline results

- **Judge model:** Gemma 4 E2B Q4_0 for all three judges, served locally by llama.cpp at temperature 0.
- **Primary endpoint:** sensitivity for the 57 High or Very high risk errors.
- **Matching rule:** the spec rule plus evidence turns (D-03).
- **Confidence intervals:** Wilson 95%.
- **Prompt hashes:** J0 `5b534af6eabd`, J1 `8fc941675800`, J2 `6fe481511c1d`.

| Judge | High-risk caught (primary) | All 174 errors | Subtle (109) | Obvious (65) | Unmatched flags per clean note |
| --- | --- | --- | --- | --- | --- |
| J0 Naive | **21/57 = 36.8%** (25.5–49.8) | 72 = 41.4% (34.3–48.8) | 46 = 42% | 26 = 40% | 0.25 |
| J1 Rubric | **38/57 = 66.7%** (53.7–77.5) | 102 = 58.6% (51.2–65.7) | 66 = 61% | 36 = 55% | 0.54 |
| J2 Claim-check | **24/57 = 42.1%** (30.2–55.0) | 78 = 44.8% (37.6–52.3) | 49 = 45% | 29 = 45% | 0.42 |

### Paired comparisons (exact McNemar, Holm-adjusted)

| Comparison | High-risk errors (only-A / only-B) | All errors (only-A / only-B) |
| --- | --- | --- |
| J1 vs J0 | 19 / 2, p_holm = 0.0004 | 39 / 9, p_holm < 0.0001 |
| J2 vs J0 | 10 / 7, p_holm = 0.63 | 28 / 22, p_holm = 0.48 |

### Under the spec-literal matching rule (`--strict-spec`)

| Judge | High-risk caught |
| --- | --- |
| J0 | 20/57 = 35.1% (24.0–48.1) |
| J1 | 34/57 = 59.6% (46.7–71.4) |
| J2 | 23/57 = 40.4% (28.6–53.3) |

J1 vs J0 is still significant (p_holm = 0.003), so the conclusion doesn't depend on the matching extension.

### Planted-error detection by type, J1 (best judge)

| Error type | Caught |
| --- | --- |
| Dose/unit | 17/18 |
| Timing | 13/14 |
| Laterality | 11/12 |
| Plan altered | 17/20 |
| Drug name swapped | 9/12 |
| Self-correction lost | 15/21 |
| Negation | 8/14 |
| Safety fact omitted | 5/20 |
| Wrong speaker | 4/16 |
| Hallucinated finding | 3/15 |
| Other fact omitted | **0/12** (no judge caught more than 1) |

### Risk grading vs the answer key, on detected errors

Weighted κ is 0.37 for J0, 0.38 for J1 and 0.21 for J2. Gwet's AC2 is 0.75, 0.69 and 0.59 respectively. J1 and J2 grade risk about half a point lower than the key on average.

The confirmatory sample size for ±0.05 precision at p = 0.80 is still **246 high-risk errors**, so this pilot of 57 can only show large differences.

## 3. How to run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m jtj.app.main
```

Then open http://localhost:8080. Re-running judges (`scripts/run_judges.py`) needs a local `llama-server` with the model; cached outputs mean an unchanged note costs no calls. `scripts/compute_metrics.py` regenerates `data/results/`.

## 4. What you must review before anyone sees it

- [x] **Cases 01–24:** all marked clinician-reviewed (2026-10-29); the "drafted for clinician review" labels are gone.
- [x] Seeded severity and likelihood ratings: your decisions of 2026-10-29 are applied, and you approved all changes (REVIEW_QUEUE).
- [x] About page wording: reviewed, and the draft labels are removed.
- [x] Judge prompts: frozen before the run (D-24, D-25).
- [ ] Protocol page wording, the GRRAS / DECIDE-AI checklist, and the "Related work" positioning.
- [ ] "Most DRUG_NAME and NEGATION errors High/Very high" (D-28). Choose: accept as is, add flips, or regrade. If you change the answer key, metrics need recomputing, but **no new LLM calls** are needed unless note text changes.
- [x] Source for the drug-name and negation weighting: cited as Protocol reference [14] (D-31).
- [x] Speaker labels: "Relative" is fine.
- [ ] Model licence (Gemma terms) before publishing results; and licence for the repo (I suggest MIT for code, CC BY 4.0 for cases).

The full list is in `REVIEW_QUEUE.md`.

## 5. Decisions and surprises

All decisions are in [`DECISIONS.md`](DECISIONS.md). The ones made on 2026-10-29 are D-25 to D-29:

- D-25: spec v2 and the re-run
- D-26: DRUG_NAME authoring
- D-27: the subtle rule
- D-28: NEGATION share
- D-29: palette and fonts

Today I also changed the Overview and Scorecard to feature **whichever judge scored best**. Before, they hard-coded J2 as "the structured judge", which would have misrepresented the result.

What surprised me:

1. **The two-step claim-check judge (J2) did no better than the naive judge** (24 vs 21 of 57, p = 0.63). The single-prompt rubric judge (J1) did clearly better. A likely cause is the small 2B model: J2's extract-then-verify chain loses errors at the extraction step. It also raised the most unmatched flags on seeded notes (42, against 21 for J1 and 12 for J0). Don't generalise this to larger models.
2. **Omissions are the blind spot.** No judge caught more than 1 of 12 "other fact omitted" errors. J1 caught only 5 of 20 safety-fact omissions, which are mostly High risk. Judges check what is in the note far better than what is missing from it.
3. **Subtle errors were caught as often as obvious ones** (J1: 61% vs 55%). This is because "obvious" mainly means omissions and negations, which are the hard types. Subtlety as defined (D-27) isn't what drives detection; error type is.
4. **The most dangerous miss:** `case_13_a_e1`, passive suicidal ideation recorded as denied (risk 25). All three judges missed it.
5. **Unmatched flags are not yet adjudicated.** Some are judge mistakes. For example, J0 called a correct 7.5 pack-year calculation wrong. Others may be real issues I didn't plant. Rater mode has an adjudication queue for this.

## 6. LLM calls

**491 of the 1,500 cap**, all made locally at no API cost:

- 72 J0 + 72 J1 + 144 J2 for each full run;
- pilot calls and the superseded spec v1 run (archived in `data/judge_outputs/superseded_spec_v1/`);
- about 72 calls to re-judge the six edited cases;
- retries.

## 7. Known issues and next steps

- **Clinician raters.** Recruit 2–3 UK clinicians, for example GP trainees or ED registrars through a regional training programme, a medical-education contact or a professional network. Give them `RATER_CODE` and ask for at least 20 notes each, blinded and in random order. Before inviting them, attach a volume for the ratings database (`DEPLOY.md` §3).
- **Agreement analysis.** Once 2 or more raters have each rated 20 or more notes, `scripts/compute_agreement.py` fills the Scorecard's clinician agreement section. It reports clinician-vs-clinician agreement (weighted κ and Gwet's AC2 on risk tier) and clinician-vs-answer-key agreement. It also gives a human baseline for how many planted errors clinicians catch, so judge sensitivity can be read against it. Adjudicating unmatched judge flags then turns "unmatched" into true or false positives.
- **Bigger sample.** The pilot has 57 high-risk errors; ±0.05 precision needs about 246, so about 4× the cases.
- **Model comparison.** A larger judge model, such as Gemma 4 E4B, would test whether J2's weak result comes from model size (stretch goal, dropped in D-18).
- **First-load speed.** The Flet web client is about 3.5 MB gzipped, so a phone's first visit takes several seconds.
- **Deployment.** This is your decision after clinical sign-off. Steps are in `DEPLOY.md`.
