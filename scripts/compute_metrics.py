"""Match judge outputs to the answer key and write data/results/{metrics,matches,flags}.json."""
import argparse
import json

import _path  # noqa: F401
from jtj.metrics import compute_all
from jtj.mutate import DATA, load_cases

ap = argparse.ArgumentParser()
ap.add_argument("--strict-spec", action="store_true", help="spec-literal omission matching (sensitivity analysis)")
args = ap.parse_args()

res = compute_all(load_cases(), DATA / "judge_outputs", strict_spec_matching=args.strict_spec)
out = DATA / "results"
suffix = "_strict" if args.strict_spec else ""
for name in ("metrics", "matches", "flags"):
    (out / f"{name}{suffix}.json").write_text(json.dumps(res[name], indent=1))
m = res["metrics"]
print(f"status={m['status']} judges={m['judges_available']} errors={m['n_errors']} high={m['n_high_errors']}")
for j, d in m["per_judge"].items():
    p = d["primary"]
    print(f"  {j}: {p['k']}/{p['n']} = {p['p']} ({p['lo']}-{p['hi']})")
