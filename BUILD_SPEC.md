# BUILD_SPEC.md: "Judge the Judge"

**A clinician-validated mini-study of LLM judges for AI-generated clinical notes**

You are building this overnight, unattended. The owner (Dr Paulina Mensah, a medical doctor and engineer) is asleep. She will review the work in the morning. Read this whole file before writing any code.

---

## 0. Operating rules for this session (read first)

1. **Work autonomously.** Do not stop to ask questions. When something is ambiguous, pick the most reasonable option and record it in `DECISIONS.md` (one line each: decision, reason, how to reverse it).
2. **Work in phases** (section 9). Commit to git at the end of every phase with a clear message, so partial progress is never lost.
3. **Never fabricate clinician data.** Clinician ratings do not exist yet. Never simulate, generate or invent clinician ratings and present them as real. Any placeholder must be visibly labelled `PLACEHOLDER` in the data and in the UI.
4. **Never present placeholder metrics as results.** If the LLM judges could not be run (for example no API key), the app must show an honest "not yet run" state, not made-up numbers.
5. **All clinical content is a draft for clinician review.** Write it carefully (UK practice, NICE/BNF-consistent), but mark every case file `"clinician_reviewed": false`. Paulina will review and flip it.
6. **No real patient data.** Everything is synthetic. Use obviously fictional names.
7. **No company branding.** This project is relevant to the work of an ambient-scribe company, but it must not use any company's name, logo, colours or product in the app, the repo, or the README, and must not claim to test any company's product. It is an *independent* study of LLM documentation judges.
8. **Do not deploy.** Prepare deployment files (section 8) but do not run a deploy. Clinical content must be reviewed first.
9. **Cost guard.** All LLM calls go through one cached client (section 5.4). Hard cap: 1,500 LLM calls total for the whole night. Log the running count.
10. **Finish with `MORNING_REPORT.md`** (section 10), even if you did not finish everything.

---

## 1. Why this exists (the research question)

Ambient AI scribes turn a consultation into a clinical note. At scale, nobody can read every note, so safety claims depend on **automated judges** (usually LLMs) that find documentation errors and grade their clinical risk. If the judge is wrong, every safety number built on it is wrong.

**Primary question:** How well does an LLM judge detect clinically important errors in AI-generated notes, and does a more structured judge design detect more high-risk errors than a naive one?

**Secondary questions:**
- Does the judge grade clinical risk the way a clinician would? (Measured when clinician ratings arrive.)
- Which error types do judges miss most? (Omissions vs hallucinations vs subtle swaps like laterality or dose.)

**Why this framing matters (keep this spirit in the app copy):**
- Word-level metrics like word error rate (WER) are poor proxies for clinical harm. What matters is the clinical risk of each error.
- A judge's agreement with clinicians must be measured and reported honestly, not assumed.
- Paulina's prior work found that LLMs rated their own first-aid answers 10–19% higher than clinicians did. This study extends that line: *who checks the checker?*

---

## 2. Study design (implement exactly; this is the scientific core)

### 2.1 Design in one paragraph

We write synthetic UK consultations, each with a transcript and a clean reference note. We then create "AI-generated" note variants by **programmatically injecting known errors** (seeded errors) into the reference note. Because we injected them, we have an exact answer key. We run three judge designs over every note and measure how many seeded errors each judge detects, by error type and risk tier. Judge flags that do not match a seeded error go to a queue for clinician adjudication (they may be false positives, or genuine issues in the base note). Clinicians later rate notes blind in the app, which unlocks agreement statistics.

### 2.2 Cases

- **24 consultations** across 6 settings, 4 each: GP (adult), GP (paediatrics), Emergency Department, mental health, outpatient specialist (e.g. cardiology, respiratory), and telephone/remote consultation.
- Each case: a realistic transcript (clinician + patient, sometimes a relative), 40–90 turns, with natural speech (hesitations, corrections, a relative interjecting, a patient correcting themselves). Include at least 6 cases where something is **said and then corrected** later in the conversation (this is where scribes fail).
- Each case: a **reference note** in UK style (presenting complaint, history, medications and allergies, examination, impression, plan, safety-netting). It must be fully supported by the transcript.
- Clinically realistic UK content: NICE-aligned management, BNF-plausible doses, UK drug names (paracetamol, not acetaminophen), NHS context (111, A&E, GP).

### 2.3 Note variants and seeded errors

- For each case create **3 variants**: one *clean* (no seeded errors; tests false-positive behaviour) and two *seeded* variants with 2–4 errors each. That gives 72 notes and roughly 130–170 seeded errors.
- Each seeded error is defined as a **mutation**: `{section, original_text, mutated_text}` applied to the reference note. A mutation with empty `mutated_text` is an omission. The original text must exist exactly once in the reference note (validate this in tests).

**Error taxonomy (use these exact type codes):**

| Code | Type | Example |
| --- | --- | --- |
| OMIT_SAFETY | Omitted safety-critical fact | Allergy, red flag, or safety-netting advice dropped |
| OMIT_OTHER | Omitted non-critical fact | Social history detail dropped |
| HALLUC | Hallucinated finding | "Chest clear" when no chest exam was discussed |
| NEGATION | Negation flip | "Denies chest pain" becomes "reports chest pain" |
| LATERALITY | Side/site swap | Left knee becomes right knee |
| DOSE_UNIT | Dose, unit or frequency error | 5 mg becomes 50 mg; BD becomes OD |
| ATTRIBUTION | Wrong speaker attribution | Mother's symptom recorded as the child's |
| TEMPORAL | Timing error | "3 days" becomes "3 weeks" |
| CORRECTION_LOST | Self-correction ignored | Note keeps the figure the patient later corrected |
| PLAN_CHANGE | Plan altered | Follow-up "1 week" becomes "if needed" |
| DRUG_NAME | Drug name swapped for a sound-alike or look-alike | "hydralazine" becomes "hydroxyzine" |

Distribute types so each appears at least 8 times across the dataset.

**Make the seeded errors realistic, not just easy to plant.** Published evaluation of production ambient scribes reports that most serious errors are **medication-name confusions** and **negation or status flips**. Weight the dataset towards these: give DRUG_NAME and NEGATION at least 12 instances each, and make most of them High or Very high risk where clinically justified.

For DRUG_NAME:
- Use sound-alike or look-alike pairs that a speech-recognition or summarisation system could plausibly confuse, preferring pairs that appear on UK look-alike/sound-alike medication safety lists. Starting set (Paulina reviews every pair): hydralazine/hydroxyzine, amlodipine/amiloride, chlorpromazine/chlorphenamine, carbamazepine/oxcarbazepine, prednisolone/propranolol, sulfasalazine/sulfadiazine.
- The swapped drug must be one the reference note actually mentions, and the mutated text must still read as a plausible note (correct dose form, plausible dose).
- Record the pair and why it is dangerous in `seeded_rationale` (for example, an antihypertensive recorded as a sedating antihistamine).

Also make some errors *subtle*: at least a third of all seeded errors should be ones a busy clinician could plausibly miss on a quick read (for example TEMPORAL "3 days" → "3 weeks", CORRECTION_LOST), not only obvious ones. Tag each seeded error with `"subtle": true|false`, and report sensitivity separately for subtle and obvious errors on the Scorecard.

### 2.4 Clinical risk grading (answer key)

For every seeded error, assign **severity (1–5)** and **likelihood of harm (1–5)**, with a one-sentence clinical rationale. Risk score = severity × likelihood. Tiers, in the style of UK digital clinical safety risk management (DCB0129/DCB0160, ISO 14971 thinking):

| Score | Tier |
| --- | --- |
| 1–4 | Low |
| 5–9 | Moderate |
| 10–15 | High |
| 16–25 | Very high |

Store these as `seeded_severity`, `seeded_likelihood`, `seeded_rationale`, all flagged `"clinician_reviewed": false`.

### 2.5 Judges (the comparators)

All judges see the **transcript and the note** and return strict JSON (schema in 5.3).

- **J0 Naive:** "Find any errors in this clinical note compared with the transcript." No rubric, no taxonomy.
- **J1 Rubric:** Given the error taxonomy and the severity/likelihood scales with anchors; asked to list errors with type, quoted note span, quoted transcript evidence, severity, likelihood and rationale.
- **J2 Claim-check:** Two steps. (a) Extract every atomic clinical claim from the note, and separately every clinically relevant fact from the transcript. (b) Verify each note claim against the transcript (supported / contradicted / unsupported) and check each transcript fact for presence in the note (to catch omissions). Then grade findings with the J1 rubric.

Use temperature 0. Run each judge on all 72 notes. **Stretch:** run J1 with two different models to show model sensitivity.

### 2.6 Matching judge findings to seeded errors

Deterministic, no LLM:
- A judge finding matches a seeded error if they are in the same note and the judge's quoted note span overlaps the mutated text (or, for omissions, the judge's quoted transcript evidence overlaps the omitted original text). Use `rapidfuzz` partial ratio ≥ 80 as the overlap test. Type agreement is recorded but is not required for a match.
- Each seeded error is either **detected** or **missed** per judge.
- Judge findings that match no seeded error are **unadjudicated flags**. Do not count them as false positives; send them to the adjudication queue. On clean notes, report the number of flags per note as a descriptive measure.
- Write unit tests for the matcher with hand-built examples, including tricky ones.

### 2.7 Endpoints and analysis plan

**Primary endpoint:** sensitivity of each judge for seeded errors in the High and Very high tiers, with Wilson 95% CIs.

**Secondary endpoints:**
- Sensitivity by error type and by tier, per judge (heatmap).
- Paired comparison J2 vs J0 and J1 vs J0 on the same seeded errors: McNemar's exact test, Holm correction across the two comparisons.
- Severity agreement between judge and answer key on detected errors: quadratic-weighted Cohen's kappa and Gwet's AC2 (ordinal weights), with case-level cluster bootstrap 95% CIs (2,000 resamples, fixed seed).
- Unadjudicated flags per clean note, per judge.
- **Unlocked once clinician ratings exist:** clinician vs judge agreement on error presence (Gwet's AC1) and on risk tier (Gwet's AC2); inter-clinician agreement; precision of judge flags after adjudication.

**Sample size reasoning (put on the Protocol page):** with ~40 high/very-high-risk seeded errors, a sensitivity near 0.80 has a 95% CI half-width of roughly ±0.13. Say plainly that this is a pilot that estimates precision, not a confirmatory study, and state what n a confirmatory study would need for ±0.05 (compute it).

**Reporting standard:** follow the spirit of GRRAS (reliability and agreement) and DECIDE-AI (describing the AI system). Include a short checklist on the Protocol page.

Implement Gwet's AC1/AC2 yourself in `stats.py` and cross-check against the `irrCAC` package if it installs; unit-test against a worked example with known values. If the two disagree, trust neither until you find out why, and log it.

### 2.8 External validity: why seeded errors (put on the Protocol page and summarise on the Overview)

Planted errors will not tell us how often a judge misses errors in real-world notes. They measure something real-note studies cannot: **an exact miss rate for known error types**, because the answer key is complete. Studies of real notes can only judge errors that something flagged, and expert reviewers miss errors too, so the true number of errors is unknown and the miss rate must be estimated statistically.

State the value plainly, with the clinical analogies:

1. **A floor test.** Like spike-and-recovery in a lab assay or a phantom in radiology QA: if a judge misses a planted tenfold dose error, it will miss subtler real ones. Passing is necessary, not sufficient.
2. **The miss rate, exactly,** by error type and risk tier.
3. **Fair comparisons.** Identical notes with one change isolate the effect of judge design, model or prompt.
4. **Cheap, repeatable regression testing.** Re-run in minutes when a model or prompt changes, with no clinician time. In production this becomes a standing check that a judge update has not started missing, for example, drug-name errors: post-market surveillance for the judge itself.
5. **No patient data,** so it can run from day one.

State the limits just as plainly:

- Planted errors may be easier, or simply different, from the errors a real scribe makes, so sensitivity here is likely an *upper bound* on real-world sensitivity for the same error types.
- Error types we did not plant are not measured at all.
- Planting is mitigated, not solved, by modelling errors on reported real-world failure modes (2.3).

Close with the recommended design: **use seeded errors alongside real-note validation** (blinded clinician review, adjudicated reference standards, latent-class or capture–recapture estimates of errors everyone missed), not instead of it. In production, real failures found in surveillance become new seeded cases, so the test set keeps up with the errors that actually occur.

---

## 3. Product: the web app

### 3.1 Who it is for

1. A **recruiter** who is not a clinician, opening a link on a phone between meetings. They need the point in 30 seconds.
2. A **hiring manager / clinical AI lead** who will scrutinise the method, the stats and the honesty of the limitations.
3. **Clinician raters** (Paulina's doctor friends) who will rate notes blind.

### 3.2 Stack

- **Python + Flet**, served as a web app, deployed on **fly.io** (Paulina has shipped Flet apps on fly.io before). Pin the Flet version in `requirements.txt` and check the installed version's API before writing UI code (Flet's API has changed between versions; do not rely on memory).
- Charts: whichever chart approach works reliably with the pinned Flet version (native Flet charts preferred; Plotly or Matplotlib images as fallback). Test that charts render.
- **The app never calls an LLM at runtime.** All judge outputs and metrics are precomputed by scripts and stored in `data/results/` as JSON. The server needs no API key.
- Rater data: SQLite at a path from env var `RATINGS_DB` (default `./data/ratings.sqlite`), so it can live on a fly.io volume later.

### 3.3 Pages (top navigation; collapses to a menu on narrow screens)

**1. Overview (landing page)**
- One-sentence headline answering the primary question with the real number, e.g. "The structured judge caught X of Y high-risk errors (Z%, 95% CI a–b); the naive judge caught …". If judges have not run, show "Results pending" instead.
- Three short cards: *The problem* (judges underpin safety claims), *What we did* (seeded errors, three judge designs), *What we found* (headline + the most-missed error type).
- An always-visible "Limitations" strip under the headline: synthetic data, pilot sample size, clinician ratings pending (until they exist).
- A clear call to action: "Try spotting the errors yourself" → Case Explorer in challenge mode.

**2. Case Explorer (the centrepiece; this is where explainability lives)**
- Case picker: filter by setting, variant, error type, risk tier, and "missed by judge X".
- Three-pane layout on desktop (stacked on mobile): **Transcript** | **Note** | **Findings**.
- **Challenge mode (default for first visit):** the answer key is hidden. The viewer reads the note and clicks any text they think is wrong, then presses "Reveal". The app shows what they caught vs missed. This makes the problem tangible to a non-clinician in one minute.
- **Explain mode:**
    - Seeded errors highlighted in the note, coloured by risk tier, with an icon for detected/missed per selected judge.
    - Clicking an error opens a side panel: error type in plain English, original vs mutated text as a diff, the transcript line(s) that prove it (auto-scroll and highlight in the transcript pane), the answer-key severity × likelihood shown on a small 5×5 risk matrix, the clinical rationale, and each judge's verdict with its own rationale and quoted evidence.
    - Judge selector (J0 / J1 / J2) to compare how each judge saw the same note.
    - Unadjudicated flags shown in a neutral colour with the label "Judge flag, not in answer key — awaiting clinician review".

**3. Judge Scorecard**
- Primary endpoint per judge: point estimate with CI whiskers (not bars alone).
- Heatmap: sensitivity by error type (rows) × judge (columns), with n in each cell. Tap a cell to jump to those cases in the Explorer.
- Sensitivity by risk tier per judge.
- Paired comparisons with McNemar p-values (Holm-adjusted) in plain language.
- Severity agreement (weighted kappa, Gwet's AC2, CIs).
- "Most dangerous misses": a list of very-high-risk errors any judge missed, each linking to the case.
- Every metric has an ⓘ explanation in plain English: what it measures, why it matters clinically, and how to read it. Example for sensitivity: "Of the errors we planted, how many did the judge find? A missed high-risk error is the failure that matters most."

**4. Rate Notes (clinician rater mode)**
- Simple access gate: a shared rater code from env var `RATER_CODE` (if unset, rater mode is disabled with a message). Raters enter initials and a professional role (free text).
- Raters see transcript + note, **blinded** to answer key and judge outputs, in randomised order (seeded per rater).
- For each note: mark erroneous spans (click to select text, or select a sentence), choose error type, severity 1–5, likelihood 1–5, optional comment. Also a whole-note rating: "safe to file as is / needs minor edits / needs major edits / unsafe".
- Also an **adjudication queue**: unadjudicated judge flags shown one at a time with the transcript: "Is this a real error?" yes / no / unsure.
- Saves to SQLite. "Export ratings (CSV)" button for the owner.
- Script `scripts/compute_agreement.py` reads ratings and regenerates the clinician-agreement results; the Scorecard's agreement section unlocks when ≥2 raters have rated ≥20 notes each.

**5. Protocol**
- Written like a short pre-registered protocol: background, question, design, cases, error taxonomy table, risk matrix, judges (with full prompts in collapsible blocks), matching rule, endpoints, analysis plan, sample size reasoning, **external validity: why seeded errors (section 2.8)**, GRRAS/DECIDE-AI checklist, limitations, version and date.
- On the Overview, add one line under the Limitations strip linking to the external validity section: "Why planted errors? They give an exact miss rate for known error types; they don't replace real-note validation."
- "Download protocol (Markdown)" button.

**6. About**
- Short, first person, in Paulina's voice (draft; she'll edit): who she is (doctor and engineer), why judge validation matters, links to her GitHub (github.com/Boadiwaa) and the medRxiv preprint she co-authored on LLMs for emergency medical help (DOI 10.1101/2024.04.17.24305971).
- A section "What I'd do next with production data": post-market surveillance using judges with drift monitoring, periodic clinician re-calibration samples, retiring judges whose agreement drops, and multilingual extension (seed the same errors into translated consultations to test whether judge sensitivity holds across languages).

### 3.4 UI and design requirements

- **Feel:** calm, clinical, trustworthy, modern. Lots of whitespace, one accent colour, neutral greys. Readable at a glance on a phone.
- **Risk tier colours** (consistent everywhere, with text labels too, never colour alone): Low = slate/grey-blue, Moderate = amber, High = orange-red, Very high = deep red. Unadjudicated = neutral purple-grey. Check contrast against WCAG AA.
- **Typography:** one clean sans-serif; transcript in a slightly smaller size with speaker labels in bold (Clinician / Patient / Relative).
- **Light and dark mode**, following the system setting with a toggle.
- **Mobile first:** the Overview must look excellent at 390px wide. Keep the first screen light so it loads fast.
- **Empty and loading states** everywhere: no blank screens, no stack traces shown to users.
- **Footer on every page:** "Synthetic data only. Independent study. Not a medical device. Clinical content drafted for clinician review." (Remove "drafted for clinician review" automatically once all cases have `clinician_reviewed: true`.)
- **Plain English first, detail on demand:** every technical term (sensitivity, Gwet's AC2, McNemar) has a tooltip or ⓘ panel.

---

## 4. Repository layout

```
judge-the-judge/
├── README.md                 # what, why, how to run, how to deploy, screenshots placeholder
├── BUILD_SPEC.md             # this file
├── DECISIONS.md
├── MORNING_REPORT.md
├── requirements.txt          # pinned
├── Dockerfile
├── fly.toml
├── .env.example              # ANTHROPIC_API_KEY, JUDGE_MODEL, RATER_CODE, RATINGS_DB
├── data/
│   ├── cases/                # case_01.json … case_24.json
│   ├── notes/                # generated note variants (from mutations)
│   ├── judge_outputs/        # raw judge JSON per judge per note
│   ├── cache/                # LLM response cache (gitignored)
│   └── results/              # metrics.json, matches.json, flags.json
├── src/jtj/
│   ├── schema.py             # pydantic models for cases, mutations, judge output
│   ├── mutate.py             # apply mutations → note variants
│   ├── llm.py                # cached, rate-limited, call-counting LLM client
│   ├── judges.py             # J0, J1, J2 prompts and runners
│   ├── match.py              # finding ↔ seeded error matcher
│   ├── stats.py              # Wilson CI, McNemar, Holm, weighted kappa, Gwet AC1/AC2, bootstrap
│   └── app/                  # Flet UI (one module per page + shared components/theme)
├── scripts/
│   ├── validate_cases.py
│   ├── build_notes.py
│   ├── run_judges.py         # --judge J0|J1|J2|all --limit N --dry-run
│   ├── compute_metrics.py
│   └── compute_agreement.py
└── tests/
```

---

## 5. Technical details

### 5.1 Case file schema (`data/cases/case_XX.json`)

```json
{
  "case_id": "case_07",
  "setting": "ED",
  "title": "Ankle injury after a fall",
  "clinician_reviewed": false,
  "transcript": [
    {"turn": 1, "speaker": "Clinician", "text": "..."},
    {"turn": 2, "speaker": "Patient", "text": "..."}
  ],
  "reference_note": {
    "presenting_complaint": "...",
    "history": "...",
    "medications_allergies": "...",
    "examination": "...",
    "impression": "...",
    "plan": "...",
    "safety_netting": "..."
  },
  "variants": [
    {"variant_id": "case_07_clean", "mutations": []},
    {
      "variant_id": "case_07_a",
      "mutations": [
        {
          "error_id": "case_07_a_e1",
          "type": "LATERALITY",
          "section": "examination",
          "original_text": "left lateral malleolus",
          "mutated_text": "right lateral malleolus",
          "evidence_turns": [14, 15],
          "seeded_severity": 3,
          "seeded_likelihood": 3,
          "seeded_rationale": "...",
          "subtle": false
        }
      ]
    }
  ]
}
```

### 5.2 Validation (`scripts/validate_cases.py`, also run in tests)

- Every `original_text` appears exactly once in its section.
- Every `evidence_turns` exists in the transcript.
- Every type code is in the taxonomy; severity and likelihood are 1–5.
- Clean variants have no mutations.
- Error type distribution meets the minimum of 8 per type; print a summary table.

### 5.3 Judge output schema (strict JSON, validated with pydantic; retry once on invalid JSON, then record as a parse failure)

```json
{
  "findings": [
    {
      "type": "NEGATION",
      "note_section": "history",
      "note_span": "reports chest pain",
      "transcript_evidence": "No, no chest pain at all.",
      "evidence_turns": [22],
      "severity": 4,
      "likelihood": 3,
      "rationale": "..."
    }
  ],
  "overall_note_safety": "needs_major_edits"
}
```

J0 may not know the taxonomy; map its free-text types to `UNSPECIFIED` and still match by span.

### 5.4 LLM client (`llm.py`)

- Provider: Anthropic API via `ANTHROPIC_API_KEY`. Model from env `JUDGE_MODEL`, default `claude-sonnet-5-5`; optional second model for the stretch goal from `JUDGE_MODEL_B`.
- Disk cache keyed by hash of (model, system prompt, user prompt, temperature). Re-runs cost nothing.
- Retries with exponential backoff on rate limits; global call counter with the hard cap from section 0; `--dry-run` prints prompts without calling.
- **If `ANTHROPIC_API_KEY` is missing at start:** build everything else, write a clear note in `MORNING_REPORT.md`, and leave the app in the "Results pending" state. Do not generate fake judge outputs.

### 5.5 Running the judges

Run order: J1 on 6 notes first, inspect the outputs and the matcher by hand, fix prompts or matcher if needed, and record any change in `DECISIONS.md`. Then run all judges on all notes. Freeze prompts once the full run starts, and record the prompt hashes in `results/metrics.json`.

---

## 6. Explainability checklist (the app must satisfy all of these)

- [ ] Every number on screen can be traced to the cases behind it in two taps.
- [ ] Every error shows *what* changed (diff), *why it matters* (rationale + risk matrix) and *the proof* (transcript lines).
- [ ] Every judge verdict shows the judge's own reasoning and quoted evidence.
- [ ] Missed errors are as visible as detected ones.
- [ ] Uncertainty is shown (CIs, n per cell), never hidden.
- [ ] Limitations are on the landing page, not buried.
- [ ] A non-clinician can understand the point from the Overview alone.

---

## 7. Tests (pytest; all must pass before the final commit)

- Case validation (5.2) over all case files, including: DRUG_NAME and NEGATION each have at least 12 instances; every DRUG_NAME mutation swaps a drug that appears in the reference note for a different drug name; at least a third of seeded errors are tagged `"subtle": true`.
- Mutation application: produces expected text; omissions remove text cleanly.
- Matcher: at least 10 hand-written cases, including near-misses and omissions.
- Stats: Wilson CI, McNemar exact, Holm, weighted kappa, Gwet AC1/AC2 against known worked values.
- Metrics pipeline end to end on a tiny fixture with known answers (a fixture clearly separate from real data).
- App smoke test: every page builds without exceptions with (a) full results and (b) no results present.

---

## 8. Deployment preparation (do not deploy)

- `Dockerfile` (slim Python base) that runs the Flet app as a web server on `0.0.0.0:8080` (or the port the pinned Flet version expects; check its docs).
- `fly.toml` with internal port matching, a health check, `auto_stop_machines` on to save cost, and a commented-out `[mounts]` section for a volume at `/data` for ratings.
- `DEPLOY.md` with exact steps: `fly launch --no-deploy`, set secrets (`RATER_CODE`), optional volume creation, `fly deploy`, and how to download the ratings database.
- Verify the Docker image builds locally if Docker is available; if not, say so in the morning report.

---

## 9. Phases (commit after each)

1. **Scaffold:** repo, pinned requirements, schema, theme, empty pages, tests running. Confirm Flet version and API.
2. **Cases:** write all 24 cases with mutations; validation passes; distribution table printed. This is the most important content: take care with clinical realism and UK conventions.
3. **Pipeline:** mutate, LLM client, judges, matcher, stats, metrics; unit tests pass.
4. **Judge run:** pilot on 6 notes, adjust, freeze, full run (if API key present).
5. **UI:** Overview, Case Explorer (challenge + explain modes), Scorecard, Protocol, About.
6. **Rater mode + adjudication + agreement script.**
7. **Polish:** mobile layout, dark mode, empty states, tooltips, accessibility pass, README with screenshots if you can capture them (Playwright against the local web app is fine), deployment files.
8. **Morning report.**

If time runs short, protect in this order: cases and validation → pipeline and stats → Overview + Case Explorer → Scorecard → Protocol → rater mode → polish.

---

## 10. MORNING_REPORT.md (write last; keep it skimmable)

1. **Status:** which phases are done, partial or not started.
2. **Headline results** (or "judges not run" and why), with the exact numbers and CIs.
3. **How to run locally:** three commands.
4. **What Paulina must review before anyone sees it,** as a checklist: each case's clinical content, every seeded severity/likelihood rating, the About page wording, judge prompts.
5. **Decisions made overnight** (link to `DECISIONS.md`) and anything surprising in the results.
6. **LLM calls used** vs the cap.
7. **Known issues and suggested next steps,** including how to recruit 2–3 clinician raters and what the agreement section will show once they finish.
