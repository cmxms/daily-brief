"""
capture_cookies.py — mint a Substack session cookie locally for cloud posting.

Substack's login is behind Cloudflare, which 403-blocks email/password login from
datacenter IPs (GitHub Actions). The workaround: log in ONCE from your own machine
(a residential IP, which passes), grab the session cookie, and store it as the
SUBSTACK_COOKIES secret. The cloud job then reuses that cookie — no login challenge.

Run locally:   python capture_cookies.py
It logs in with SUBSTACK_EMAIL/SUBSTACK_PASSWORD from .env and writes the cookie string
to .substack_cookies.txt (gitignored). Then push it to GitHub as a secret:

    gh secret set SUBSTACK_COOKIES < .substack_cookies.txt
    rm .substack_cookies.txt          # don't leave the session token on disk

Re-run this whenever cloud posting starts failing with a 403 (cookies expire over time).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from substack import Api

HERE = Path(__file__).resolve().parent
OUT = HERE / ".substack_cookies.txt"

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def _load_dotenv() -> None:
    f = HERE / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and not os.environ.get(k):
            os.environ[k] = v


def main() -> int:
    _load_dotenv()
    email = os.environ.get("SUBSTACK_EMAIL", "").strip()
    password = os.environ.get("SUBSTACK_PASSWORD", "").strip()
    pub = os.environ.get("SUBSTACK_PUBLICATION_URL", "").strip().rstrip("/")
    if not (email and password):
        print("need SUBSTACK_EMAIL + SUBSTACK_PASSWORD in .env")
        return 1
    api = Api(email=email, password=password, publication_url=pub or None)
    cookie_str = "; ".join(f"{k}={v}" for k, v in api._session.cookies.get_dict().items())
    OUT.write_text(cookie_str, encoding="utf-8")
    print(f"captured {len(cookie_str.split(';'))} cookies -> {OUT.name}")
    print("next:  gh secret set SUBSTACK_COOKIES < .substack_cookies.txt  &&  rm .substack_cookies.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
