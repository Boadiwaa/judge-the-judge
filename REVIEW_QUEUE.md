# Review queue (needs a human: Paulina)

Items are added as the build progresses. Tick them off and flip flags in the data where noted.

## Blocking (nothing can proceed without you)

- [x] ~~Provide `ANTHROPIC_API_KEY`~~ Superseded 2026-10-28: judges now run locally on open-weight models (DECISIONS D-14).
- [ ] **Choose the judge model(s) for the full run.** Pilot on Gemma 4 E2B Q4_0: see the pilot notes below. MedGemma 1.5 4B **Q3_K_M** looped and produced no usable output on the one note tried. Options: (a) Gemma 4 E2B only; (b) also compress the **Gemma 4 E4B** in your Hugging Face cache to Q4_K_M (larger, likely better); (c) download a lighter-compressed MedGemma (Q4_K_M or Q8_0) for a general-vs-medical comparison. Time: about 1 minute per J1 call on E2B, so a full J0+J1+J2 run is about 5 hours per model.
- [ ] **Check the model licences** (Gemma terms of use; MedGemma Health AI Developer Foundations terms) before publishing results.
- [ ] **Decide whether to deploy.** Spec forbids deploying before clinical review. `DEPLOY.md` has the steps.

## Clinical content (must review before anyone sees the app)

- [ ] Every case in `data/cases/` — transcript realism, UK practice, NICE/BNF consistency. Flip `"clinician_reviewed": true` per case when happy. (The footer drops "drafted for clinician review" automatically once all 24 are true.)
- [ ] Every seeded error's `seeded_severity`, `seeded_likelihood`, `seeded_rationale` (answer key). A table view: `python scripts/validate_cases.py --table`.
- [ ] Judge prompts in `src/jtj/judges.py` (J0/J1/J2) — freeze before the full run.
- [ ] About page wording (written in your voice as a draft).
- [ ] Protocol page wording and the GRRAS / DECIDE-AI checklist.

## Environment / verification gaps

- [ ] Docker not installed on this machine: Dockerfile is unverified. Run `docker build -t jtj .` once.
- [ ] Set `RATER_CODE` secret before sharing rater mode.

## Items added during the build

<!-- appended below as work proceeds -->

- [x] **Matching rule for omissions (DECISIONS D-03).** Approved 2026-10-28: extension is primary, spec-literal reported alongside. I extended the spec rule so a judge quoting the transcript lines that prove an omitted fact counts as a detection. Approve, or say "spec-literal only" and I'll make `--strict-spec` the primary analysis. This changes the primary endpoint, so it should be fixed *before* the judges run (pre-registration).
- [ ] **Answer-key grading calls I was least sure of:**
  - `case_07_a_e2` penicillin allergy dropped (ED ankle): S4 × L4 = 16, Very high. I justified it via perioperative flucloxacillin if the fracture needs fixing. The mockup showed 20; is 16 right?
  - `case_13_a_e1` passive suicidal ideation recorded as denied: S5 × L3 = 15, High (just below Very high). Arguably L4.
  - `case_09_b_e2` febrile-child red flags omitted: S5 × L2 = 10. Low likelihood because the advice was given verbally; check you agree with this reasoning, which I applied to all safety-netting omissions.
- [ ] **Paediatric doses in case_09** (3-year-old, assumed ~14 kg; weight is not stated in the transcript): paracetamol 180 mg QDS, ibuprofen 100 mg TDS, amoxicillin 250 mg TDS × 5 days (NICE NG91 back-up). Should the clinician state the weight?
- [ ] **Apixaban dosing logic in case_17** (age 72, 58 kg, creatinine 98 → 5 mg BD, none of the dose-reduction criteria met).
- [ ] **Nitrofurantoin in possible early pregnancy (case_21).** The clinician says it is suitable early in pregnancy, avoids trimethoprim implicitly and defers ibuprofen. Check the wording matches current UKHSA/BNF guidance.
