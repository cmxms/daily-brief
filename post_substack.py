"""
post_substack.py — publish the brief to Substack as a DRAFT via python-substack.

Logs in with your Substack account and creates a draft from the brief's Markdown
(headers, bold, and code-block grids render natively — `Post.from_markdown` handles
the conversion). Draft-only by default: review and hit Publish in Substack yourself.

Creds (env / .env, or GitHub Actions secrets):
  SUBSTACK_EMAIL, SUBSTACK_PASSWORD, SUBSTACK_PUBLICATION_URL

NOTE: Substack login can occasionally trip bot-protection (captcha / email code). If a
login fails, log in once in a browser first, then retry; persistent failures mean we
switch to the cookie-string auth path instead of email/password.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from substack import Api
from substack.post import Post

# Windows consoles default to cp1252 and choke on the ☀️/emoji in the title — force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _load_dotenv() -> None:
    """Load ./.env for local runs; real env vars (GitHub Actions secrets) always win."""
    f = Path(__file__).resolve().parent / ".env"
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


_load_dotenv()


def split_title(brief_md: str) -> tuple[str, str]:
    """First '# ...' line -> post title; the rest -> body markdown."""
    lines = brief_md.splitlines()
    title, start = "Morning Brief", 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith("# "):
            title = ln.strip()[2:].strip()
            start = i + 1
            break
    return title, "\n".join(lines[start:]).strip()


def post(brief_md: str, publish: bool = False) -> str:
    email = os.environ.get("SUBSTACK_EMAIL", "").strip()
    password = os.environ.get("SUBSTACK_PASSWORD", "").strip()
    pub_url = os.environ.get("SUBSTACK_PUBLICATION_URL", "").strip().rstrip("/")
    missing = [n for n, v in [("SUBSTACK_EMAIL", email), ("SUBSTACK_PASSWORD", password),
                              ("SUBSTACK_PUBLICATION_URL", pub_url)] if not v]
    if missing:
        raise RuntimeError(f"missing env for posting: {', '.join(missing)}")

    api = Api(email=email, password=password, publication_url=pub_url)
    user_id = api.get_user_id()

    title, body_md = split_title(brief_md)
    p = Post(title=title,
             subtitle="Daily market situational awareness — not financial advice.",
             user_id=user_id)
    p.from_markdown(body_md, api=api)

    draft = api.post_draft(p.get_draft())
    draft_id = draft.get("id")
    if publish:
        api.prepublish_draft(draft_id)
        api.publish_draft(draft, send=False, share_automatically=False)
        return f"PUBLISHED '{title}' (draft {draft_id})"
    return f"DRAFT created: '{title}' (id {draft_id}) — review at {pub_url}/publish/home"


if __name__ == "__main__":
    import sys
    src = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding="utf-8").read()
    print(post(src, publish="--publish" in sys.argv))
