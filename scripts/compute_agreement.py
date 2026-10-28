"""Read clinician ratings (RATINGS_DB) and regenerate data/results/agreement.json.

The Scorecard's clinician-agreement section unlocks when >= 2 raters have rated >= 20 notes each.
"""
import json
import math

import _path  # noqa: F401
from jtj.agreement import compute
from jtj.app.data import load
from jtj.app.rating_status import connect, db_path
from jtj.mutate import DATA


def clean(x):
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


con = connect()
if con is None:
    raise SystemExit(f"No ratings database at {db_path()}.")
d = load()
res = clean(compute(con, d.cases, d, d.matches, d.flags))
(DATA / "results" / "agreement.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: res[k] for k in ("unlocked", "progress")}, indent=1))
