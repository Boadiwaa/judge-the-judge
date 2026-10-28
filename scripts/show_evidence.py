"""Print each seeded error with the transcript turns it cites (for clinical review)."""
import sys

import _path  # noqa: F401
from jtj.mutate import load_cases

only = set(sys.argv[1:])
for c in load_cases():
    if only and c.case_id not in only:
        continue
    t = {x.turn: x for x in c.transcript}
    for v in c.variants:
        for m in v.mutations:
            print(f"{m.error_id:<14} {m.type:<16}" + " | ".join(f"{n}:{t[n].text[:42]}" for n in m.evidence_turns))
