# Judge the Judge

**A clinician-validated mini-study of LLM judges for AI-generated clinical notes.**

Ambient AI scribes turn consultations into notes, and at scale their safety claims rest on automated
judges that find documentation errors. If the judge is wrong, every safety number built on it is wrong.
This project asks *who checks the checker?*

I planted 174 known errors (omissions, negation flips, wrong side, dose slips and more) in 72 AI-style
notes written from 24 synthetic UK consultations. Three LLM judge designs (naive, rubric, and
claim-by-claim checking) were run over every note and scored against the exact answer key, with
confidence intervals. Clinicians can then rate the notes blind to validate both the answer key and the
judges.

It is an independent study on synthetic data. It is not a medical device, and it does not test any
company's product.

## What's in the app

| Page | What it shows |
| --- | --- |
| Overview | The headline result, the limitations, and how the study works |
| Case Explorer | Transcript, note and findings. **Challenge mode:** spot the errors yourself. **Explain mode:** each error's change, transcript proof, risk matrix and each judge's verdict |
| Scorecard | Sensitivity with 95% CIs, a heatmap by error type, paired comparisons, severity agreement, dangerous misses. Every number links to its cases |
| Rate notes | Blinded clinician rating and judge-flag adjudication (needs `RATER_CODE`) |
| Protocol | Pre-registered-style protocol, generated from the code, with full prompts; downloadable |
| About | Why I built this, and what I'd do next |

_Screenshots: to add once results are final._

## Run locally (three commands)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m jtj.app.main
```

Then open http://localhost:8080. The app reads `data/cases/` and `data/results/`. It never calls a model.

## The pipeline

```
data/cases/*.json ──validate_cases.py──► build_notes.py ──► run_judges.py ──► compute_metrics.py ──► data/results/
                                                             (local Gemma via                   │
                                                              llama.cpp; cached)                ▼
                         ratings.sqlite ──────────────────► compute_agreement.py ──────────► agreement.json
```

- **Judges** run offline on an open-weight model (Gemma 4 E2B, 4-bit) served by `llama-server`, at
  temperature 0 with schema-constrained JSON. Every response is cached by hash, so re-runs are free.
  See `DEPLOY.md` for the exact commands.
- **Matching** is deterministic (`src/jtj/match.py`): rapidfuzz partial ratio ≥ 80 between the judge's
  quoted span and the planted change.
- **Statistics** (`src/jtj/stats.py`): Wilson CIs, exact McNemar with Holm correction, weighted kappa,
  and Gwet's AC1/AC2 implemented from first principles and cross-checked against `irrCAC`, plus a
  case-level cluster bootstrap.

## Repository map

```
src/jtj/            schema, mutate, match, stats, llm, judges, metrics, agreement, protocol
src/jtj/app/        Flet web app (main.py, pages/, components, theme, data loader)
scripts/            validate_cases, build_notes, run_judges, compute_metrics, compute_agreement, show_evidence
data/cases/         24 case files (transcript, reference note, seeded variants, answer key)
data/results/       metrics.json, matches.json, flags.json (+ *_strict.json sensitivity analysis)
tests/              ~100 pytest tests: matcher, stats, pipeline fixture, cases, app smoke tests, rater mode
```

## Deploy

See [DEPLOY.md](DEPLOY.md). Clinical content must be reviewed first; see [REVIEW_QUEUE.md](REVIEW_QUEUE.md).
Decisions made along the way are in [DECISIONS.md](DECISIONS.md).

## Links

- Author: Dr Paulina Mensah · [github.com/Boadiwaa](https://github.com/Boadiwaa)
- Related preprint: LLMs for emergency medical help, [doi:10.1101/2024.04.17.24305971](https://doi.org/10.1101/2024.04.17.24305971)
