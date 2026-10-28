# Review queue (needs a human: Paulina)

Items are added as the build progresses. Tick them off and flip flags in the data where noted.

## Blocking (nothing can proceed without you)

- [x] ~~Provide `ANTHROPIC_API_KEY`~~ Superseded 2026-10-28: judges now run locally on open-weight models (DECISIONS D-14).
- [x] **Choose the judge model(s) for the full run.** Decided 2026-10-28: Gemma 4 E2B only (D-18). Pilot on Gemma 4 E2B Q4_0: see the pilot notes below. MedGemma 1.5 4B **Q3_K_M** looped and produced no usable output on the one note tried. Options: (a) Gemma 4 E2B only; (b) also compress the **Gemma 4 E4B** in your Hugging Face cache to Q4_K_M (larger, likely better); (c) download a lighter-compressed MedGemma (Q4_K_M or Q8_0) for a general-vs-medical comparison. Time: about 1 minute per J1 call on E2B, so a full J0+J1+J2 run is about 5 hours per model.
- [ ] **Check the model licences** (Gemma terms of use; MedGemma Health AI Developer Foundations terms) before publishing results.
- [ ] **Decide whether to deploy.** Spec forbids deploying before clinical review. `DEPLOY.md` has the steps.

## Clinical content (must review before anyone sees the app)

- [ ] Every case in `data/cases/` — transcript realism, UK practice, NICE/BNF consistency. Flip `"clinician_reviewed": true` per case when happy. (The footer drops "drafted for clinician review" automatically once all 24 are true.)
- [ ] Every seeded error's `seeded_severity`, `seeded_likelihood`, `seeded_rationale` (answer key). A table view: `python scripts/validate_cases.py --table`.
- [ ] Judge prompts in `src/jtj/judges.py` (J0/J1/J2) — freeze before the full run.
- [ ] About page wording (written in your voice as a draft).
- [ ] Protocol page wording and the GRRAS / DECIDE-AI checklist.

## Environment / verification gaps

- [x] ~~Docker not installed~~ Docker Desktop installed and the image built and tested locally (2026-10-28).
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

### Clinical calls in cases 02–24 I'd most like checked (added 2026-10-28)

- [ ] **case_06 (head injury, 81-year-old):** apixaban 2.5 mg BD is the reduced dose. Age ≥80 is one criterion, but her weight and creatinine aren't stated, so the record doesn't show she meets two. Add a weight, or change to 5 mg BD? I also left CT timing as "within the next few hours" rather than citing the NG232 time limit.
- [ ] **case_05 (chest pain, possible NSTEMI):** the plan has aspirin (from the ambulance crew) plus fondaparinux, with no second antiplatelet loading dose. I left that to cardiology. Is that realistic for a UK ED note?
- [ ] **case_03 (diabetes hypo):** the case gives sulfonylurea driving advice but doesn't address whether he must tell the DVLA after one severe hypo needing help from someone else. Should it?
- [ ] **case_20 (first seizure):** the seizure was partly provoked by sleep deprivation. I used the standard "usually 6 months off driving" wording. DVLA may treat provoked seizures differently; please check.
- [ ] **case_10 (bronchiolitis):** managed at home with next-day review at about 50% of usual feeds, RR 54 and SpO2 95%. Is this borderline call one you'd make?
- [ ] **Very high grades in new cases:** methotrexate weekly recorded as daily (case_19, S5×L4 = 20), sick-day rules dropped for an 85-year-old (case_24, 16), "no intent to harm the baby" recorded as an urge to harm (case_16, 16), anticoagulant dropped from a head-injury note (case_06, 20).
- [ ] **Speaker labels:** the spec allows only Clinician, Patient and Relative. Partners, a wife who witnessed a seizure, and a son on speakerphone are all labelled "Relative". In cases 10 and 23 the patient is a baby, so every non-clinician turn is a "Relative" (two parents in case_10).

### UI (added 2026-10-28)

- [ ] **Heading font:** the mockups use a serif for display headings. Flutter web can't use system fonts, so headings are currently sans-serif. Pick a font (for example Source Serif 4, SIL Open Font License) and I'll bundle it (DECISIONS D-22).
- [ ] **First-load speed on phones:** Flet's web client is about 3.5 MB even gzipped, and takes several seconds to start on a cold visit. If that's too slow for recruiters, the alternative is a small static HTML landing page in front of the app (a design change from the spec; your call).
- [ ] **About page wording** (`src/jtj/app/pages/about.py`): drafted in your voice and marked DRAFT on the page.
- [ ] **Protocol "Related work" and "References"** (`src/jtj/protocol.py`): 13 references, each checked against its publisher or arXiv record on 2026-10-28. Check you're happy with how the study is positioned ("well-established designs, not the frontier").

### Spec update 2026-10-28 (§2.3 drug names, subtle errors; DECISIONS D-25 to D-28)

- [ ] **Drug-name pairs (spec: "Paulina reviews every pair").** 12 `DRUG_NAME` errors; `python scripts/validate_cases.py --table` lists them. Please check each pair is a realistic confusion and the grade is right:
  - amlodipine → amiloride (case_05_a, case_06_a), 4×3 = 12 High: hyperkalaemia once an ACE inhibitor is added.
  - penicillin → penicillamine allergy (case_06_b), 5×3 = 15 High.
  - salbutamol → salmeterol "as required" (case_08_a asthma 5×3 = 15; case_18_a COPD 4×3 = 12).
  - sulfasalazine → sulfadiazine intolerance (case_19_a), 4×3 = 12.
  - metformin → metronidazole (case_22_a 3×3 = 9; case_24_a 3×2 = 6, as the plan still says stop metformin).
  - clobetasone → clobetasol (case_11_a, retyped from DOSE_UNIT, 3×3 = 9).
  - **Weakest, please check:** sertraline → Seroquel (case_14_a, 3×3), atorvastatin → rosuvastatin (case_01_a, 2×2), omeprazole → esomeprazole (case_02_a, 1×2). I don't know of a UK look-alike/sound-alike list that includes these three; I added them because the spec's other pairs don't appear in any note. Replace any you don't like.
- [ ] **"Most DRUG_NAME and NEGATION errors High or Very high."** DRUG_NAME: 6 of 12 are High. NEGATION: 5 of 14. I graded on clinical merit rather than raising grades to hit "most". Options: accept as is; add a few genuinely high-risk negation flips (more errors to review); or regrade.
- [ ] **Subtle/obvious tags** on all 174 errors (rule in D-27; 109 subtle). Tags were applied by rule plus overrides, not one by one, so please skim them while you review each case.
- [ ] **Source for "most serious errors are drug-name confusions and negation flips".** The protocol says this without a citation, because I haven't verified which publication the spec means. Give me the reference, or ask me to find and check one.
- [ ] **Total errors is 174**, slightly above the spec's "roughly 130–170".
- [ ] **Reload any case file you have open.** I added errors to 11 case files and a `"subtle"` field to every error in all 24, while you were reviewing. If your editor has unsaved changes to a case file, saving it may overwrite mine, so tell me and I'll merge.
