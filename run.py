"""
run.py — orchestrate the daily brief: gather -> write -> (optionally) post.

  python run.py            # gather + write, save to out/, print it. Does NOT post.
  python run.py --post     # also email it to Substack (creates a draft)
  python run.py --gather-only   # just the data block (no Claude call), for testing

Each step writes its artifact under out/ so you can inspect what happened.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gather as G

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="email the brief to Substack (draft)")
    ap.add_argument("--gather-only", action="store_true", help="stop after the data block")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    data = G.gather()
    date = data["date"]
    block = G.render_md(data)
    (OUT / f"{date}.data.md").write_text(block, encoding="utf-8")
    print(f"[1/3] gathered data block -> out/{date}.data.md", flush=True)
    if args.gather_only:
        print(block)
        return 0

    import write_brief as W
    print(f"[2/3] writing brief with {W.MODEL} (+ web search)...", flush=True)
    brief = W.write_brief(block)
    brief_path = OUT / f"{date}.brief.md"
    brief_path.write_text(brief, encoding="utf-8")
    print(f"      -> out/{date}.brief.md\n")
    print(brief)

    if args.post:
        import post_substack as P
        print(f"\n[3/3] creating Substack draft...", flush=True)
        print("      " + P.post(brief))
    else:
        print("\n[3/3] skipped posting (run with --post to publish a draft).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
