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

# US equity-market full-day closures (2026 + early 2027). A brief on a closed day is
# pointless, so --skip-holidays makes the scheduled run a clean no-op on these (the cron
# already covers weekends via 1-5). Refresh yearly; e.g. 2026-07-03 = Independence Day
# observed (Jul 4 falls on a Saturday → Friday close).
US_MARKET_HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}


def is_trading_day(d) -> bool:
    """True on weekdays that aren't a US market holiday."""
    return d.weekday() < 5 and d.isoformat() not in US_MARKET_HOLIDAYS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="email the brief to Substack (draft)")
    ap.add_argument("--discord", action="store_true", help="post the brief to Discord (webhook)")
    ap.add_argument("--gather-only", action="store_true", help="stop after the data block")
    ap.add_argument("--skip-holidays", action="store_true",
                    help="exit 0 without doing anything on weekends / US market holidays (for the cron)")
    args = ap.parse_args()

    from datetime import date
    if args.skip_holidays and not is_trading_day(date.today()):
        print(f"[skip] {date.today().isoformat()} is not a US trading day — no brief today.", flush=True)
        return 0

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

    if args.discord:
        import post_discord as D
        print(f"\n[3/3] posting to Discord...", flush=True)
        print("      " + D.post(brief))
    elif args.post:
        import post_substack as P
        print(f"\n[3/3] creating Substack draft...", flush=True)
        print("      " + P.post(brief))
    else:
        print("\n[3/3] skipped posting (run with --discord to post, or --post for a Substack draft).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
