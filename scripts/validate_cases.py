"""Validate all case files and print the error-type distribution. --table prints the answer key."""
import argparse
import sys

import _path  # noqa: F401
from jtj.mutate import load_cases
from jtj.schema import ERROR_TYPES, TIERS, risk_tier
from jtj.validate import dataset_targets, validate_dataset

ap = argparse.ArgumentParser()
ap.add_argument("--table", action="store_true", help="print every seeded error for clinical review")
args = ap.parse_args()

cases = load_cases()
problems, counts = validate_dataset(cases)
targets = dataset_targets(cases, counts)
errs = [m for c in cases for v in c.variants for m in v.mutations]
print(f"{len(cases)} cases, {sum(len(c.variants) for c in cases)} notes, {len(errs)} seeded errors, "
      f"{sum(c.has_correction for c in cases)} cases with a correction\n")
print(f"{'type':<16}{'n':>4}   " + "  ".join(f"{t:>9}" for t in TIERS))
for t in ERROR_TYPES:
    tiers = [sum(1 for m in errs if m.type == t and m.tier == tr) for tr in TIERS]
    print(f"{t:<16}{counts[t]:>4}   " + "  ".join(f"{x:>9}" for x in tiers))
print(f"{'TOTAL':<16}{len(errs):>4}   " + "  ".join(f"{sum(m.tier == tr for m in errs):>9}" for tr in TIERS))
if args.table:
    print()
    for c in cases:
        for v in c.variants:
            for m in v.mutations:
                print(f"{m.error_id:<16}{m.type:<16}S{m.seeded_severity}xL{m.seeded_likelihood}={m.risk_score:<3}"
                      f"{risk_tier(m.risk_score):<10}{m.original_text!r} -> {m.mutated_text!r}\n{'':<16}{m.seeded_rationale}")
if problems:
    print("\nPROBLEMS:\n  " + "\n  ".join(problems))
if targets:
    print("\nDATASET TARGETS NOT YET MET:\n  " + "\n  ".join(targets))
sys.exit(1 if problems else 0)
