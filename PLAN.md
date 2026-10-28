# Build plan: Judge the Judge

Reviewable plan derived from `BUILD_SPEC.md` and the five UI mockups. Anything that needs a human
(Paulina) is collected in [`REVIEW_QUEUE.md`](REVIEW_QUEUE.md); judgement calls made without asking
are in [`DECISIONS.md`](DECISIONS.md).

## Environment found (2026-10-28)

| Item | State | Consequence |
| --- | --- | --- |
| Python | 3.12.2 (miniconda) | venv in `.venv/` |
| Flet | 1.0.5 pinned (latest) | 1.x API checked before UI code |
| Judge models | Local open-weight models via llama.cpp (D-14): Gemma 4 E2B Q4_0 works; MedGemma 1.5 4B Q3_K_M looped | 6-note J1 pilot done ([PILOT_NOTES.md](PILOT_NOTES.md)); Gemma 4 E2B only (D-18); full run restarted after the spec update (D-25) |
| Docker | Docker Desktop installed | Image built and tested locally (not deployed) |
| flyctl | installed | Not used: spec forbids deploying |
| git | available, folder was not a repo | `git init` in `judge-the-judge/`, commit per phase |

## Phases

| # | Phase | Deliverables | Done when |
| --- | --- | --- | --- |
| 1 | Scaffold | repo layout (spec §4), pinned `requirements.txt`, `schema.py`, theme, page stubs, pytest running | `pytest` green, app boots |
| 2 | Cases | 24 case JSONs (6 settings × 4), 3 variants each, 2–4 mutations per seeded variant, ≥8 per error type, ≥6 said-then-corrected | `validate_cases.py` passes, distribution table printed |
| 3 | Pipeline | `mutate.py`, `llm.py` (cache, cap 1,500, backoff, dry-run), `judges.py` (J0/J1/J2), `match.py`, `stats.py`, `compute_metrics.py` | unit tests incl. matcher ≥10 cases, stats vs worked values, irrCAC cross-check, tiny end-to-end fixture |
| 4 | Judge run | pilot J1 on 6 notes → inspect → freeze → full run | Pilot done. Full run restarted 2026-10-28 on the re-frozen prompts after the spec update (D-25) |
| 5 | UI | Overview, Case Explorer (challenge + explain), Scorecard, Protocol, About | **Done** (2026-10-28): all pages built and smoke-tested with and without results; checked in a browser at 1280px and 390px, light and dark |
| 6 | Rater mode | rater gate (`RATER_CODE`), blinded randomised rating, adjudication queue, SQLite, CSV export, `compute_agreement.py` | **Done**: rater flow works end to end locally |
| 7 | Polish + deploy prep | mobile 390px, dark mode toggle, empty states, ⓘ panels, WCAG AA tier colours, Dockerfile, `fly.toml`, `DEPLOY.md`, README | **Done**: checked in browser; Docker image built and tested locally |
| 8 | Morning report | `MORNING_REPORT.md` per spec §10 | written last |

Protection order if time runs out (spec §9): cases → pipeline/stats → Overview + Explorer → Scorecard → Protocol → rater mode → polish.

## Key design choices (details in DECISIONS.md)

- **Results pending is the default state.** Every results-bearing widget reads `data/results/metrics.json`; if absent, it renders a labelled empty state. The mockups' `[X]`, `[Z]%` placeholders are never filled with invented numbers.
- **Matcher** is pure Python + rapidfuzz `partial_ratio ≥ 80`, normalised (lowercase, whitespace collapsed). Omissions match on transcript evidence *or* note span against the omitted original text.
- **Stats** implemented from first principles in `stats.py` (Wilson, exact McNemar via binomial, Holm, quadratic weighted kappa, Gwet AC1/AC2 with ordinal weights, case-cluster bootstrap seed 20261028), cross-checked against `irrCAC`.
- **Confirmatory n** for ±0.05 at p=0.80 (Wilson/normal approx): n ≈ 1.96²·0.8·0.2/0.05² ≈ 246 high-risk errors.
- **UI** follows the mockups: serif display headings, one blue accent, tier colours with text labels, three-pane explorer stacking on mobile.
