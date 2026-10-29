# Review queue (needs a human: Paulina)

Items are added as the build progresses. Tick them off and flip flags in the data where noted.

## Blocking (nothing can proceed without you)

- [x] ~~Provide `ANTHROPIC_API_KEY`~~ Superseded 2026-10-28: judges now run locally on open-weight models (DECISIONS D-14).
- [x] **Choose the judge model(s) for the full run.** Decided 2026-10-28: Gemma 4 E2B only (D-18). Pilot on Gemma 4 E2B Q4_0: see the pilot notes below. MedGemma 1.5 4B **Q3_K_M** looped and produced no usable output on the one note tried. Options: (a) Gemma 4 E2B only; (b) also compress the **Gemma 4 E4B** in your Hugging Face cache to Q4_K_M (larger, likely better); (c) download a lighter-compressed MedGemma (Q4_K_M or Q8_0) for a general-vs-medical comparison. Time: about 1 minute per J1 call on E2B, so a full J0+J1+J2 run is about 5 hours per model.
- [ ] **Check the model licences** (Gemma terms of use; MedGemma Health AI Developer Foundations terms) before publishing results.
- [x] **Decide whether to deploy.** 2026-10-29: Paulina asked to deploy after clinical review; live at https://judge-the-judge.fly.dev (one machine, lhr, rater mode off until `RATER_CODE` is set). Spec forbids deploying before clinical review. `DEPLOY.md` has the steps.

## Clinical content (must review before anyone sees the app)

- [x] Every case in `data/cases/` (2026-10-29: Paulina marked cases 03–24 reviewed; all 24 are now `clinician_reviewed: true`) — transcript realism, UK practice, NICE/BNF consistency. Flip `"clinician_reviewed": true` per case when happy. (The footer drops "drafted for clinician review" automatically once all 24 are true.)
- [x] Every seeded error's `seeded_severity`, `seeded_likelihood`, `seeded_rationale` (answer key). A table view: `python scripts/validate_cases.py --table`.
- [x] Judge prompts in `src/jtj/judges.py` (J0/J1/J2) — freeze before the full run.
- [x] About page wording: reviewed by Paulina 2026-10-29; draft labels removed.
- [ ] Protocol page wording and the GRRAS / DECIDE-AI checklist.

## Environment / verification gaps

- [x] ~~Docker not installed~~ Docker Desktop installed and the image built and tested locally (2026-10-28).
- [ ] Set `RATER_CODE` secret before sharing rater mode.

## Items added during the build

<!-- appended below as work proceeds -->

- [x] **Matching rule for omissions (DECISIONS D-03).** Approved 2026-10-28: extension is primary, spec-literal reported alongside. I extended the spec rule so a judge quoting the transcript lines that prove an omitted fact counts as a detection. Approve, or say "spec-literal only" and I'll make `--strict-spec` the primary analysis. This changes the primary endpoint, so it should be fixed *before* the judges run (pre-registration).
- [x] **Answer-key grading calls I was least sure of:** 2026-10-29: case_07 kept at 16; case_13 likelihood raised to 5 (25, Very high).
  - `case_07_a_e2` penicillin allergy dropped (ED ankle): S4 × L4 = 16, Very high. I justified it via perioperative flucloxacillin if the fracture needs fixing. The mockup showed 20; is 16 right?
  - `case_13_a_e1` passive suicidal ideation recorded as denied: S5 × L3 = 15, High (just below Very high). Arguably L4.
  - ~~`case_09_b_e2` febrile-child red flags omitted: S5 × L2 = 10.~~ Decided 2026-10-29: L3 for all spoken-but-unrecorded safety-netting omissions.
- [x] **Paediatric doses in case_09** Resolved 2026-10-29: weight (14 kg) now measured in the transcript and recorded in the examination. Original item: (3-year-old, assumed ~14 kg; weight is not stated in the transcript): paracetamol 180 mg QDS, ibuprofen 100 mg TDS, amoxicillin 250 mg TDS × 5 days (NICE NG91 back-up). Should the clinician state the weight?
- [x] **Apixaban dosing logic in case_17** 2026-10-29: dose is now 2.5 mg BD, with creatinine raised from 98 to 140 so she meets two reduction criteria (weight ≤60 kg, creatinine ≥133). The planted dose error is now 2.5 → 5 mg (overdose, bleeding risk). (age 72, 58 kg, creatinine 98 → 5 mg BD, none of the dose-reduction criteria met).
- [x] **Nitrofurantoin in possible early pregnancy (case_21).** 2026-10-29: course changed to 7 days. The clinician says it is suitable early in pregnancy, avoids trimethoprim implicitly and defers ibuprofen. Check the wording matches current UKHSA/BNF guidance.

### Clinical calls in cases 02–24 I'd most like checked (added 2026-10-28)

- [x] **case_06 (head injury, 81-year-old):** 2026-10-29: dose kept (criteria may be in her previous records). Grades decided 2026-10-29: dropped anticoagulant 5×3 = 15; amlodipine → amiloride 4×4 = 16. Apixaban dose question still open: apixaban 2.5 mg BD is the reduced dose. Age ≥80 is one criterion, but her weight and creatinine aren't stated, so the record doesn't show she meets two. Add a weight, or change to 5 mg BD? I also left CT timing as "within the next few hours" rather than citing the NG232 time limit.
- [x] **case_05 (chest pain, possible NSTEMI):** Kept as is (2026-10-29). the plan has aspirin (from the ambulance crew) plus fondaparinux, with no second antiplatelet loading dose. I left that to cardiology. Is that realistic for a UK ED note?
- [x] **case_03 (diabetes hypo):** 2026-10-29: DVLA advice added. the case gives sulfonylurea driving advice but doesn't address whether he must tell the DVLA after one severe hypo needing help from someone else. Should it?
- [x] **case_20 (first seizure):** 2026-10-29: wording kept. the seizure was partly provoked by sleep deprivation. I used the standard "usually 6 months off driving" wording. DVLA may treat provoked seizures differently; please check.
- [x] **case_10 (bronchiolitis):** 2026-10-29: changed to same-day hospital referral (intercostal recession, feeds about half). managed at home with next-day review at about 50% of usual feeds, RR 54 and SpO2 95%. Is this borderline call one you'd make?
- [x] **Very high grades in new cases:** Superseded by the 2026-10-29 decisions (case_06 and case_19 regraded); case_16 and case_24 are listed under the remaining grade checks. methotrexate weekly recorded as daily (case_19, S5×L4 = 20), sick-day rules dropped for an 85-year-old (case_24, 16), "no intent to harm the baby" recorded as an urge to harm (case_16, 16), anticoagulant dropped from a head-injury note (case_06, 20).
- [x] **Speaker labels:** 2026-10-29: Paulina: "Relative" is fine. the spec allows only Clinician, Patient and Relative. Partners, a wife who witnessed a seizure, and a son on speakerphone are all labelled "Relative". In cases 10 and 23 the patient is a baby, so every non-clinician turn is a "Relative" (two parents in case_10).

### UI (added 2026-10-28)

- [x] **Heading font:** Resolved 2026-10-29: Source Serif 4 headings, Inter body, JetBrains Mono numbers, bundled (D-29). Original item: the mockups use a serif for display headings. Flutter web can't use system fonts, so headings are currently sans-serif. Pick a font (for example Source Serif 4, SIL Open Font License) and I'll bundle it (DECISIONS D-22).
- [ ] **First-load speed on phones:** Flet's web client is about 3.5 MB even gzipped, and takes several seconds to start on a cold visit. If that's too slow for recruiters, the alternative is a small static HTML landing page in front of the app (a design change from the spec; your call).
- [x] **About page wording**: reviewed 2026-10-29; DRAFT label removed.
- [ ] **Protocol "Related work" and "References"** (`src/jtj/protocol.py`): 13 references, each checked against its publisher or arXiv record on 2026-10-28. Check you're happy with how the study is positioned ("well-established designs, not the frontier").

### Spec update 2026-10-28 (§2.3 drug names, subtle errors; DECISIONS D-25 to D-28)

- [x] **Drug-name pairs (spec: "Paulina reviews every pair").** 12 `DRUG_NAME` errors; `python scripts/validate_cases.py --table` lists them. Please check each pair is a realistic confusion and the grade is right:
  - amlodipine → amiloride (case_05_a, case_06_a), 4×3 = 12 High: hyperkalaemia once an ACE inhibitor is added.
  - penicillin → penicillamine allergy (case_06_b), 5×3 = 15 High.
  - salbutamol → salmeterol "as required" (case_08_a asthma 5×3 = 15; case_18_a COPD 4×3 = 12).
  - sulfasalazine → sulfadiazine intolerance (case_19_a), 4×3 = 12.
  - metformin → metronidazole (case_22_a 3×3 = 9; case_24_a 3×2 = 6, as the plan still says stop metformin).
  - clobetasone → clobetasol (case_11_a, retyped from DOSE_UNIT, 3×3 = 9).
  - **Weakest, please check:** sertraline → Seroquel (case_14_a, 3×3), atorvastatin → rosuvastatin (case_01_a, 2×2), omeprazole → esomeprazole (case_02_a, 1×2). I don't know of a UK look-alike/sound-alike list that includes these three; I added them because the spec's other pairs don't appear in any note. Replace any you don't like.
- [ ] **"Most DRUG_NAME and NEGATION errors High or Very high."** DRUG_NAME: 6 of 12 are High. NEGATION: 5 of 14. I graded on clinical merit rather than raising grades to hit "most". Options: accept as is; add a few genuinely high-risk negation flips (more errors to review); or regrade.
- [x] **Subtle/obvious tags** on all 174 errors (rule in D-27; 109 subtle). Tags were applied by rule plus overrides, not one by one, so please skim them while you review each case.
- [x] **Source for "most serious errors are drug-name confusions and negation flips".** 2026-10-29: cited as reference [14] (Bergman et al., medRxiv 2026, doi:10.64898/2026.09.10.26362715), verified against the preprint text. It supports *serious* errors being dominated by these types, not that they are the most common overall, so the Protocol keeps "serious". Company name omitted per spec §1.7; the reference notes the authors work for an ambient-scribe developer (D-31). The protocol says this without a citation, because I haven't verified which publication the spec means. Give me the reference, or ask me to find and check one.
- [x] **Total errors is 174**, slightly above the spec's "roughly 130–170".
- [x] **Reload any case file you have open.** I added errors to 11 case files and a `"subtle"` field to every error in all 24, while you were reviewing. If your editor has unsaved changes to a case file, saving it may overwrite mine, so tell me and I'll merge.

### Decisions from Paulina, 2026-10-29

- [x] case_06: dropped anticoagulant L4 → **L3** (5×3 = 15, High): she would likely still be scanned given her symptoms. Amlodipine → amiloride L3 → **L4** (16, Very high). Rationale text updated to match.
- [x] case_19: methotrexate daily L4 → **L2** (5×2 = 10, High); I added "weekly-dose safeguards… make it unlikely to reach the patient" to the rationale, please check the wording. Sulfasalazine → sulfadiazine L3 → **L4** (16, Very high).
- [x] case_14: sertraline → Seroquel kept as is.
- [x] case_05: amlodipine → amiloride L3 → **L4** (16, Very high). Antiplatelet question: keep as is.
- [x] case_09: weight added (14 kg at examination).
- [x] Safety-netting omissions where the advice was spoken but not recorded: L2 → **L3** for all ten (case_01_b_e2, 02_a_e2, 03_a_e3, 07_b_e3, 09_b_e2, 10_b_e3, 11_b_e3, 12_b_e3, 13_b_e3, 19_b_e3). Later readers (GP, 111, medicolegal review) only have the note, and parents forget verbal advice. Severity 4 becomes 12, severity 5 becomes 15; all High.

- [x] Paulina approved all changes to date on 2026-10-29: drug-name pairs and grades, subtle/obvious tags, 174 errors, the case_09 weight, and the safety-netting L3 rule.
