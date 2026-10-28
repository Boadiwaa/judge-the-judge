"""Run judges over note variants. Usage: --judge J0|J1|J2|all --limit N --dry-run [--model M]"""
import argparse
import json
import os
from pathlib import Path

import _path  # noqa: F401
from jtj.judges import JUDGES, run_judge
from jtj.llm import LLM, CallCapReached, NoApiKey, ServerUnavailable
from jtj.mutate import DATA, build_variant_notes, load_cases

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / ".env").exists():
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())

ap = argparse.ArgumentParser()
ap.add_argument("--judge", default="all", choices=[*JUDGES, "all"])
ap.add_argument("--limit", type=int, default=None, help="max notes per judge")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--model", default=None, help="override JUDGE_MODEL (stretch: model sensitivity)")
ap.add_argument("--variants", default=None, help="comma-separated variant ids to run (pilot)")
args = ap.parse_args()

llm = LLM(model=args.model, dry_run=args.dry_run)
if not args.dry_run:
    try:
        llm.check_ready()
    except (NoApiKey, ServerUnavailable) as e:
        raise SystemExit(f"{e}\nUse --dry-run to inspect prompts. No outputs written.")
print(f"provider={llm.provider} model={llm.model}")

judges = list(JUDGES) if args.judge == "all" else [args.judge]
work = [(c, vid, secs) for c in load_cases() for vid, secs in build_variant_notes(c).items()]
if args.variants:
    keep = set(args.variants.split(","))
    work = [w for w in work if w[1] in keep]
if args.limit:
    work = work[: args.limit]

# Outputs are filed per model; compute_metrics reads data/judge_outputs/<judge> (DECISIONS D-15)
suffix = f"_{llm.model}"
try:
    for j in judges:
        out_dir = DATA / "judge_outputs" / f"{j}{suffix}"
        out_dir.mkdir(parents=True, exist_ok=True)
        for c, vid, secs in work:
            rec = run_judge(j, llm, c, secs)
            if rec["error"] == "dry_run":
                continue
            (out_dir / f"{vid}.json").write_text(json.dumps(rec, indent=1))
            nf = len(rec["output"]["findings"]) if rec["output"] else "ERR"
            print(f"{j} {vid}: findings={nf} {rec['error'] or ''}")
except (CallCapReached, NoApiKey, ServerUnavailable) as e:
    print(f"STOPPED: {e}")
print(f"LLM calls used so far: {llm.calls_used}/{llm.hard_cap}")
