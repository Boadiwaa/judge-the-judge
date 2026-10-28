# Review queue (needs a human: Paulina)

Items are added as the build progresses. Tick them off and flip flags in the data where noted.

## Blocking (nothing can proceed without you)

- [ ] **Provide `ANTHROPIC_API_KEY`** (in `.env`, see `.env.example`), then run `python scripts/run_judges.py --judge J1 --limit 6` (pilot), inspect, then `--judge all`. Until then the app shows "Results pending" everywhere. Estimated calls: J0 72 + J1 72 + J2 ~216 (3 steps) ≈ 360, well under the 1,500 cap.
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

- [ ] **Matching rule for omissions (DECISIONS D-03).** I extended the spec rule so a judge quoting the transcript lines that prove an omitted fact counts as a detection. Approve, or say "spec-literal only" and I'll make `--strict-spec` the primary analysis. This changes the primary endpoint, so it should be fixed *before* the judges run (pre-registration).
- [ ] **Answer-key grading calls I was least sure of:**
  - `case_07_a_e2` penicillin allergy dropped (ED ankle): S4 × L4 = 16, Very high. I justified it via perioperative flucloxacillin if the fracture needs fixing. The mockup showed 20; is 16 right?
  - `case_13_a_e1` passive suicidal ideation recorded as denied: S5 × L3 = 15, High (just below Very high). Arguably L4.
  - `case_09_b_e2` febrile-child red flags omitted: S5 × L2 = 10. Low likelihood because the advice was given verbally; check you agree with this reasoning, which I applied to all safety-netting omissions.
- [ ] **Paediatric doses in case_09** (3-year-old, assumed ~14 kg; weight is not stated in the transcript): paracetamol 180 mg QDS, ibuprofen 100 mg TDS, amoxicillin 250 mg TDS × 5 days (NICE NG91 back-up). Should the clinician state the weight?
- [ ] **Apixaban dosing logic in case_17** (age 72, 58 kg, creatinine 98 → 5 mg BD, none of the dose-reduction criteria met).
- [ ] **Nitrofurantoin in possible early pregnancy (case_21).** The clinician says it is suitable early in pregnancy, avoids trimethoprim implicitly and defers ibuprofen. Check the wording matches current UKHSA/BNF guidance.
