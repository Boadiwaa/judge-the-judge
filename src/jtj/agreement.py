"""Clinician agreement analysis (BUILD_SPEC §2.7 "unlocked", §3.3.4). Pure function of the ratings DB,
the answer key and the judge matches; writes data/results/agreement.json via scripts/compute_agreement.py.

Units of analysis:
- Error presence: each (seeded error, clinician) pair in a note that clinician rated. A clinician
  "found" the error if they marked a sentence overlapping the mutated text, or marked "something
  missing" in the section of an omission. Judges' detection comes from matches.json.
- Risk tier: the same pairs, restricted to errors both the clinician and the judge found, comparing
  the tier of their severity × likelihood.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict

from . import stats
from .schema import TIERS, Case, risk_tier

UNLOCK_RATERS = 2
UNLOCK_NOTES = 20


def _clinician_found(spans: list[dict], m, variant_spans) -> dict | None:
    """Return the clinician span that catches seeded error m, or None."""
    for s in spans:
        if s["section"] != m.section:
            continue
        if m.is_omission:
            if s["start_pos"] == -1:
                return s
            continue
        loc = next((v for v in variant_spans if v.mutation.error_id == m.error_id), None)
        if loc and s["start_pos"] < loc.end and s["end_pos"] > loc.start:
            return s
    return None


def compute(con: sqlite3.Connection, cases: list[Case], data, matches: dict, flags: list[dict]) -> dict:
    con.row_factory = sqlite3.Row
    raters = {r["rater_id"]: f"{r['initials']} ({r['role']})" for r in con.execute("SELECT * FROM raters")}
    notes_by_rater = defaultdict(set)
    for r in con.execute("SELECT rater_id, variant_id, overall FROM note_ratings"):
        notes_by_rater[r["rater_id"]].add(r["variant_id"])
    spans = defaultdict(list)
    for r in con.execute("SELECT * FROM span_ratings"):
        spans[(r["rater_id"], r["variant_id"])].append(dict(r))

    progress = [{"rater": raters[rid], "notes": len(notes_by_rater.get(rid, ()))} for rid in raters]
    qualified = [rid for rid in raters if len(notes_by_rater.get(rid, ())) >= UNLOCK_NOTES]
    out = {"unlock_rule": f">= {UNLOCK_RATERS} raters with >= {UNLOCK_NOTES} notes each", "progress": progress,
           "unlocked": len(qualified) >= UNLOCK_RATERS}
    if not out["unlocked"]:
        return out

    # ---- per (error, clinician) presence and tiers
    found: dict[tuple[str, int], dict | None] = {}
    error_case = {}
    for c in cases:
        for v in c.variants:
            vspans = {sec: data.spans(v.variant_id, sec) for sec in {m.section for m in v.mutations}}
            for m in v.mutations:
                error_case[m.error_id] = c.case_id
                for rid in qualified:
                    if v.variant_id in notes_by_rater[rid]:
                        found[(m.error_id, rid)] = _clinician_found(spans[(rid, v.variant_id)], m, vspans[m.section])
    errors = {e for e, _ in found}

    # clinician sensitivity against the answer key (a human baseline for the judges)
    hits = [eid for (eid, _), s in found.items() if s]
    p, lo, hi = stats.wilson(len(hits), len(found))
    out["clinician_sensitivity"] = {"k": len(hits), "n": len(found), "p": p, "lo": lo, "hi": hi}

    # inter-clinician agreement on presence (AC1) and tier (AC2), errors x raters with missing
    rows_presence = [[(1 if found.get((e, r)) else 0) if (e, r) in found else None for r in qualified] for e in errors]
    out["inter_clinician_presence_ac1"] = stats.gwet_ac1(rows_presence, [0, 1])
    rows_tier = []
    for e in errors:
        row = []
        for r in qualified:
            s = found.get((e, r))
            row.append(risk_tier(s["severity"] * s["likelihood"]) if s else None)
        rows_tier.append(row)
    out["inter_clinician_tier_ac2"] = stats.gwet_ac2(rows_tier, TIERS, "ordinal")

    # clinician vs each judge
    per_judge = {}
    for j, det in matches.items():
        pairs = [(e, r) for (e, r) in found if e in det]
        pres = [(int(det[e]["detected"]), int(bool(found[(e, r)]))) for e, r in pairs]
        tiers = []
        for e, r in pairs:
            s, f = found[(e, r)], det[e].get("finding") or {}
            if s and det[e]["detected"] and f.get("severity") and f.get("likelihood"):
                tiers.append((error_case[e], risk_tier(f["severity"] * f["likelihood"]),
                              risk_tier(s["severity"] * s["likelihood"])))
        ac2 = (stats.cluster_bootstrap(tiers, lambda x: x[0], lambda xs: stats.gwet_ac2([(a, b) for _, a, b in xs],
                                                                                        TIERS, "ordinal"))
               if len(tiers) >= 5 else (None, None, None))
        per_judge[j] = {
            "presence_ac1": stats.gwet_ac1(pres, [0, 1]) if pres else None, "presence_n": len(pres),
            "tier_ac2": {"est": ac2[0], "lo": ac2[1], "hi": ac2[2]}, "tier_n": len(tiers),
        }

    # precision of judge flags after adjudication (majority of 'yes'/'no' votes; 'unsure' ignored)
    votes = defaultdict(list)
    for r in con.execute("SELECT flag_id, verdict FROM adjudications"):
        if r["verdict"] in ("yes", "no"):
            votes[r["flag_id"]].append(r["verdict"] == "yes")
    for j in per_judge:
        decided = [sum(v) > len(v) / 2 for f, v in votes.items() if f.startswith(f"{j}:") and sum(v) * 2 != len(v)]
        n_flags = sum(1 for f in flags if f["judge"] == j)
        per_judge[j]["flags_adjudicated"] = len(decided)
        per_judge[j]["flags_total"] = n_flags
        per_judge[j]["flags_real_share"] = (sum(decided) / len(decided)) if decided else None
    out["per_judge"] = per_judge
    return out
