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


def _smart_title(s: str) -> str:
    """Title-Case a heading while preserving all-caps tokens (SPY, VIX, US) and
    tokens with digits (24h, VIX9D), and leaving emoji/punctuation alone."""
    def cap(w: str) -> str:
        letters = [c for c in w if c.isalpha()]
        if letters and all(c.isupper() for c in letters):
            return w                       # SPY, US, AI -> keep
        if any(c.isdigit() for c in w):
            return w                        # 24h, VIX9D -> keep
        for i, c in enumerate(w):
            if c.isalpha():
                return w[:i] + c.upper() + w[i + 1:]
        return w                            # emoji / punctuation
    return " ".join(cap(w) for w in s.split(" "))


def _normalize_md(md: str) -> str:
    """Guarantee a blank line before and after each heading line — otherwise
    python-substack's from_markdown merges the heading with the next paragraph
    (and stops parsing **bold** inside it)."""
    lines = md.split("\n")
    out: list[str] = []
    for i, ln in enumerate(lines):
        is_head = ln.lstrip().startswith("#")
        if is_head and out and out[-1].strip() != "":
            out.append("")
        out.append(ln)
        if is_head and i + 1 < len(lines) and lines[i + 1].strip() != "":
            out.append("")
    return "\n".join(out)


def _polish_headings(body: dict) -> None:
    """from_markdown emits huge level-2, lower-case headings. Shrink to level 3
    and Title-Case the text in place."""
    for node in body.get("content", []):
        if node.get("type") == "heading":
            node.setdefault("attrs", {})["level"] = 3
            for t in node.get("content", []):
                if t.get("type") == "text":
                    t["text"] = _smart_title(t["text"])


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
    cookies = os.environ.get("SUBSTACK_COOKIES", "").strip()
    email = os.environ.get("SUBSTACK_EMAIL", "").strip()
    password = os.environ.get("SUBSTACK_PASSWORD", "").strip()
    pub_url = os.environ.get("SUBSTACK_PUBLICATION_URL", "").strip().rstrip("/")
    if not pub_url:
        raise RuntimeError("missing env for posting: SUBSTACK_PUBLICATION_URL")

    # Prefer COOKIE auth. Email/password login is blocked by Cloudflare from
    # datacenter IPs (GitHub Actions runners get a 403 "Just a moment..." challenge),
    # so the cloud must reuse a session cookie captured from a residential IP. Run
    # `python capture_cookies.py` locally to mint the SUBSTACK_COOKIES secret; refresh
    # it if cloud posting later starts 403-ing (Substack cookies expire eventually).
    if cookies:
        api = Api(cookies_string=cookies, publication_url=pub_url)
    elif email and password:
        api = Api(email=email, password=password, publication_url=pub_url)
    else:
        raise RuntimeError("need SUBSTACK_COOKIES, or SUBSTACK_EMAIL + SUBSTACK_PASSWORD")
    user_id = api.get_user_id()

    title, body_md = split_title(brief_md)
    p = Post(title=title,
             subtitle="Daily market situational awareness — not financial advice.",
             user_id=user_id)
    p.from_markdown(_normalize_md(body_md), api=api)
    _polish_headings(p.draft_body)

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
