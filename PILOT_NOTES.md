# J1 pilot: Gemma 4 E2B (Q4_0), 2026-10-28

BUILD_SPEC §5.5 asks for a hand-inspected pilot on 6 notes before the full run. **This is a check that the pipeline and matcher work, not a result.** Sixteen errors in six notes, chosen by me, is far too few to estimate anything, and these notes are also part of the evaluation set.

**Setup:** J1 (rubric) prompt, llama.cpp build 11669, temperature 0, seed 20261028, constrained JSON. About 55 s per note on an M3 Pro. No parse failures.

| Note | Findings | Planted errors caught | Notes |
| --- | --- | --- | --- |
| case_01_clean | 1 | none planted | One false alarm: smoking history flagged as an omission, but it is in the note. |
| case_07_a (ED ankle) | 2 | 2 of 3 | Caught wrong-side ankle and paracetamol ×6. **Missed the dropped penicillin allergy (Very high).** |
| case_09_b (febrile 3-year-old) | 0 | 0 of 4 | Called the note `safe_as_is` despite the missing 999 red flags, an invented neck exam and a changed antibiotic plan. |
| case_13_a (depression) | 1 | 1 of 3 | Caught the sertraline dose. **Missed suicidal ideation recorded as denied (High).** |
| case_17_a (AF clinic) | 1 | 1 of 3 | Caught the apixaban dose. Missed the dropped rectal bleeding. |
| case_21_b (telephone UTI) | 1 | 1 of 3 | Caught the corrected duration. Missed the made-up exam and the dropped pregnancy call-back. |

**Totals:** 5 of 16 planted errors caught, 3 of 8 High/Very high.

**Patterns worth checking in the full run**
- It caught swapped numbers and sides (dose, laterality): 5 of 6.
- It caught **none** of the omissions (0 of 4) or invented findings (0 of 3). This matches the spec's hypothesis that naive and rubric judges struggle most with omissions, and it's the case for J2's claim-by-claim check.
- Its severity grades were close to the answer key where it caught something (within one point on each scale).

**Matcher check**
- The wider omission rule (D-03) changed nothing here because there were no omission catches to credit.
- The spec-literal and extended rules gave identical results.

**Prompt changes**
- None. I didn't tune the prompts against these notes, because they're part of the test set and tuning would inflate the results. If you want prompt tuning, it should use separate development cases.
