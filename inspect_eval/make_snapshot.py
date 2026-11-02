"""Freeze the LTBv1-eval subset into the JSONL snapshot the Inspect task reads.

The Inspect Evals register requires pinned assets, so the task never fetches
the live (growing) LTBv1.json. Re-run this and commit the result to refresh it:

    python inspect_eval/make_snapshot.py path/to/LTBv1.json
"""

import argparse
import json
from pathlib import Path

FIELDS = [
    "id",
    "source_text",
    "source_lang",
    "target_lang",
    "source_lang_iso",
    "target_lang_iso",
    "source_instructions",
    "verification_rules",
    "linguistics",
    "attribution",
]

args = argparse.ArgumentParser()
args.add_argument("data", type=Path, help="full LTBv1.json")
args.add_argument("--out", type=Path, default=Path(__file__).parent / "LTBv1-eval.jsonl")
args = args.parse_args()

with open(args.data, encoding="utf-8") as f:
    rows = [r for r in json.load(f) if "LTBv1-eval" in r["tags"]]

# the eval subset is text-only, which the Inspect task relies on
assert not any(r["source_media"] for r in rows)

with open(args.out, "w", encoding="utf-8") as f:
    f.writelines(json.dumps({k: r[k] for k in FIELDS}, ensure_ascii=False) + "\n" for r in sorted(rows, key=lambda r: r["id"]))

print(f"wrote {len(rows)} items to {args.out}")
