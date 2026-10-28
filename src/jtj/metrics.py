"""Metrics pipeline: judge outputs + answer key -> results JSON (BUILD_SPEC §2.6, §2.7).

Pure function of (cases, judge outputs); no LLM. `compute_all` is used by scripts/compute_metrics.py
and by the end-to-end fixture test.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from . import stats
from .match import match_note
from .schema import ERROR_TYPES, TIERS, Case, Finding, risk_tier

HIGH_TIERS = {"High", "Very high"}


def _prop(ids_hit: list[str], ids_all: list[str]) -> dict:
    p, lo, hi = stats.wilson(len(ids_hit), len(ids_all))
    clean = lambda x: None if math.isnan(x) else round(x, 4)
    return {"k": len(ids_hit), "n": len(ids_all), "p": clean(p), "lo": clean(lo), "hi": clean(hi),
            "error_ids": ids_all, "detected_ids": ids_hit}


def load_outputs(outputs_dir: Path, judge: str) -> dict[str, dict]:
    d = outputs_dir / judge
    return {p.stem: json.loads(p.read_text()) for p in sorted(d.glob("*.json"))} if d.exists() else {}


def compute_all(cases: list[Case], outputs_dir: Path, judges=("J0", "J1", "J2"),
                strict_spec_matching: bool = False, n_boot: int = stats.BOOTSTRAP_N, model: str | None = None) -> dict:
    """model: read outputs from data/judge_outputs/<judge>_<model>; None reads <judge>/ (fixtures)."""
    errors = []  # flat answer key
    for c in cases:
        for v in c.variants:
            for m in v.mutations:
                errors.append({"error_id": m.error_id, "case_id": c.case_id, "variant_id": v.variant_id,
                               "type": m.type, "tier": m.tier, "score": m.risk_score,
                               "severity": m.seeded_severity, "likelihood": m.seeded_likelihood,
                               "description": m.description or ERROR_TYPES[m.type]})
    n_notes = sum(len(c.variants) for c in cases)

    matches: dict[str, dict] = {}
    flags: list[dict] = []
    per_judge: dict[str, dict] = {}
    available = []

    for j in judges:
        outs = load_outputs(outputs_dir, f"{j}_{model}" if model else j)
        if not outs:
            continue
        available.append(j)
        det: dict[str, dict] = {}
        parse_failures, clean_flags = [], []
        for c in cases:
            turn_text = None if strict_spec_matching else {t.turn: t.text for t in c.transcript}
            for v in c.variants:
                rec = outs.get(v.variant_id)
                if rec is None or rec.get("output") is None:
                    if rec is not None:
                        parse_failures.append(v.variant_id)
                    # no output => every seeded error counts as missed (conservative; DECISIONS D-04)
                    for m in v.mutations:
                        det[m.error_id] = {"detected": False, "finding": None, "no_output": True}
                    continue
                findings = [Finding.model_validate(f) for f in rec["output"]["findings"]]
                nm = match_note(findings, v.mutations, turn_text)
                for m in v.mutations:
                    i = nm.detected[m.error_id]
                    det[m.error_id] = {"detected": i is not None,
                                       "finding": findings[i].model_dump() if i is not None else None,
                                       "type_agree": nm.type_agree.get(m.error_id)}
                for i in nm.unmatched:
                    flags.append({"flag_id": f"{j}:{v.variant_id}:{i}", "judge": j, "case_id": c.case_id,
                                  "variant_id": v.variant_id, "finding": findings[i].model_dump()})
                if v.kind == "clean":
                    clean_flags.append(len(nm.unmatched))
        matches[j] = det

        hit = lambda subset: [e["error_id"] for e in subset if det[e["error_id"]]["detected"]]
        ids = lambda subset: [e["error_id"] for e in subset]
        high = [e for e in errors if e["tier"] in HIGH_TIERS]
        by_type = {t: _prop(hit(s), ids(s)) for t in ERROR_TYPES if (s := [e for e in errors if e["type"] == t])}
        by_tier = {t: _prop(hit(s), ids(s)) for t in TIERS if (s := [e for e in errors if e["tier"] == t])}

        # severity agreement on detected errors that carry a judge severity
        pairs = [(e["case_id"], e["severity"], det[e["error_id"]]["finding"]["severity"])
                 for e in errors if det[e["error_id"]]["detected"] and det[e["error_id"]]["finding"]["severity"]]
        sev = {"n": len(pairs)}
        if len(pairs) >= 5:
            cats = [1, 2, 3, 4, 5]
            kfn = lambda xs: stats.weighted_kappa([a for _, a, _ in xs], [b for _, _, b in xs], cats)
            gfn = lambda xs: stats.gwet_ac2([(a, b) for _, a, b in xs], cats, "ordinal")
            sev["kappa_w"] = dict(zip(("est", "lo", "hi"), stats.cluster_bootstrap(pairs, lambda x: x[0], kfn, n_boot)))
            sev["gwet_ac2"] = dict(zip(("est", "lo", "hi"), stats.cluster_bootstrap(pairs, lambda x: x[0], gfn, n_boot)))
            sev["judge_minus_key_mean"] = round(sum(b - a for _, a, b in pairs) / len(pairs), 3)

        per_judge[j] = {
            "primary": _prop(hit(high), ids(high)),
            "overall": _prop(hit(errors), ids(errors)),
            "by_type": by_type,
            "by_tier": by_tier,
            "severity_agreement": sev,
            "clean_flags_per_note": {"mean": round(sum(clean_flags) / len(clean_flags), 3) if clean_flags else None,
                                     "n_notes": len(clean_flags), "counts": clean_flags},
            "notes_judged": len(outs),
            "parse_failures": parse_failures,
        }

    # paired comparisons vs J0 on the same seeded errors
    comparisons = []
    for a in ("J2", "J1"):
        if a in matches and "J0" in matches:
            for scope, subset in (("high", [e for e in errors if e["tier"] in HIGH_TIERS]), ("all", errors)):
                r = stats.mcnemar_from_pairs([matches[a][e["error_id"]]["detected"] for e in subset],
                                             [matches["J0"][e["error_id"]]["detected"] for e in subset])
                comparisons.append({"a": a, "b": "J0", "scope": scope, **r})
    for scope in ("high", "all"):
        group = [c for c in comparisons if c["scope"] == scope]
        for c, p in zip(group, stats.holm([c["p"] for c in group])):
            c["p_holm"] = p

    dangerous = []
    for e in sorted(errors, key=lambda e: -e["score"]):
        if e["tier"] != "Very high":
            continue
        missed_by = [j for j in available if not matches[j][e["error_id"]]["detected"]]
        if missed_by:
            dangerous.append({**e, "missed_by": missed_by})

    complete = len(available) == len(judges) and all(per_judge[j]["notes_judged"] == n_notes for j in judges)
    status = "pending" if not available else ("complete" if complete else "partial")
    from .judges import prompt_hashes

    return {
        "metrics": {
            "status": status, "generated": date.today().isoformat(), "judges_available": available,
            "n_cases": len(cases), "n_notes": n_notes, "n_errors": len(errors),
            "n_high_errors": sum(e["tier"] in HIGH_TIERS for e in errors),
            "judge_model": model,
            "matching_rule": "spec_literal" if strict_spec_matching else "spec_plus_evidence_turns",
            "prompt_hashes": prompt_hashes(), "per_judge": per_judge, "comparisons": comparisons,
            "most_dangerous_misses": dangerous[:15],
            "confirmatory_n_for_pm005": stats.n_for_halfwidth(0.8, 0.05),
        },
        "matches": matches,
        "flags": flags,
        "answer_key": errors,
    }


def answer_key_summary(cases: list[Case]) -> dict:
    """Results-independent summary for the UI (works before judges run)."""
    errs = [m for c in cases for v in c.variants for m in v.mutations]
    return {
        "n_cases": len(cases), "n_notes": sum(len(c.variants) for c in cases), "n_errors": len(errs),
        "by_type": {t: sum(m.type == t for m in errs) for t in ERROR_TYPES},
        "by_tier": {t: sum(risk_tier(m.risk_score) == t for m in errs) for t in TIERS},
        "all_reviewed": bool(cases) and all(c.clinician_reviewed for c in cases),
    }
