"""
post_discord.py — publish the brief to a Discord channel via an incoming webhook.

Why this exists: the Substack path can't run from the cloud (Cloudflare blocks datacenter
IPs). Discord webhooks have no such block, so this lets the WHOLE pipeline run unattended on
a free GitHub Actions cron — the point of the vacation automation.

Discord caps a message at 2000 chars, so we split the brief into ordered chunks on section
(`## `) boundaries and send them as sequential messages. Markdown (`##`, **bold**, ``` code
blocks ```) renders natively in Discord; the brief is already formatted for it (grids in code
blocks, not tables). Code fences are kept balanced across a split.

Creds (env / .env, or GitHub Actions secret):
  DISCORD_WEBHOOK_URL   (Server Settings -> Integrations -> Webhooks -> New Webhook -> Copy URL)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

LIMIT = 1900   # under Discord's 2000 hard cap, with margin for safety


def _load_dotenv() -> None:
    """Load ./.env for local runs; real env vars (Actions secrets) always win."""
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


def _split_long(section: str) -> list[str]:
    """Hard-split a single oversize section by lines, keeping ``` code fences balanced
    (close the fence at a break, reopen it on the next message). Rare safety net."""
    out: list[str] = []
    buf, in_code = "", False
    for ln in section.split("\n"):
        candidate = ln if not buf else buf + "\n" + ln
        if len(candidate) > LIMIT and buf:
            out.append(buf + ("\n```" if in_code else ""))
            buf = ("```\n" + ln) if in_code else ln
        else:
            buf = candidate
        if ln.lstrip().startswith("```"):
            in_code = not in_code
    if buf:
        out.append(buf)
    return out


def chunk(brief_md: str) -> list[str]:
    """Split the brief into <=LIMIT-char messages on `## ` section boundaries.
    The title + TL;DR ride in the first chunk; each section packs in greedily."""
    lines = brief_md.strip("\n").split("\n")
    sections: list[str] = []
    cur: list[str] = []
    for ln in lines:
        if ln.startswith("## ") and cur:
            sections.append("\n".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        sections.append("\n".join(cur))

    msgs: list[str] = []
    buf = ""
    for sec in (s.strip("\n") for s in sections):
        if not sec:
            continue
        if len(sec) > LIMIT:
            if buf:
                msgs.append(buf)
                buf = ""
            msgs.extend(_split_long(sec))
        elif buf and len(buf) + 2 + len(sec) > LIMIT:
            msgs.append(buf)
            buf = sec
        else:
            buf = sec if not buf else buf + "\n\n" + sec
    if buf:
        msgs.append(buf)
    return msgs


def _send(webhook: str, content: str) -> None:
    """POST one message; retry on Discord's 429 rate-limit. allowed_mentions is locked
    to [] so nothing in the brief text can ever trigger an @everyone/@here/role ping."""
    for _ in range(4):
        r = requests.post(webhook, json={"content": content, "allowed_mentions": {"parse": []}}, timeout=20)
        if r.status_code == 429:
            wait = 2.0
            try:
                wait = float(r.json().get("retry_after", 2.0))
            except Exception:
                pass
            time.sleep(wait + 0.5)
            continue
        r.raise_for_status()
        return
    raise RuntimeError("Discord webhook failed after retries (429)")


def _redact(url: str) -> str:
    """A Discord webhook URL ends in /webhooks/<id>/<TOKEN> — never log the token."""
    parts = url.rstrip("/").split("/")
    return "/".join(parts[:-1] + ["****"]) if len(parts) >= 2 else "****"


def _webhooks_from_env() -> list[str]:
    """Collect all configured webhook URLs (multi-server fan-out). Reads DISCORD_WEBHOOK_URL
    (the original; may itself hold several URLs) AND DISCORD_WEBHOOK_URLS (plural, for a second
    server kept as its own secret). Either may be comma- / whitespace- / newline-separated. Order
    preserved, duplicates dropped."""
    import re
    raw = " ".join(v for v in (os.environ.get("DISCORD_WEBHOOK_URL", ""),
                               os.environ.get("DISCORD_WEBHOOK_URLS", "")) if v)
    seen: set[str] = set()
    out: list[str] = []
    for u in (s.strip() for s in re.split(r"[,\s]+", raw) if s.strip()):
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _post_one(webhook: str, msgs: list[str]) -> None:
    """Send every chunk to ONE webhook, in order, with gentle pacing under the rate limit."""
    for i, m in enumerate(msgs):
        _send(webhook, m)
        if i < len(msgs) - 1:
            time.sleep(0.7)


def post(brief_md: str, webhook: str | list[str] | None = None) -> str:
    """Post the brief to every configured Discord webhook (fan-out to N servers).

    `webhook` overrides the env (a single URL or a list); otherwise the URLs come from
    DISCORD_WEBHOOK_URL (+ DISCORD_WEBHOOK_URLS). Each webhook is delivered independently: if one
    server's webhook fails (deleted/expired/rate-limited out), the others still get the brief and
    we only raise if EVERY webhook failed — so adding a friend's server can't break your own feed."""
    if webhook is None:
        webhooks = _webhooks_from_env()
    elif isinstance(webhook, str):
        webhooks = [webhook.strip()] if webhook.strip() else []
    else:
        webhooks = [w.strip() for w in webhook if w and w.strip()]
    if not webhooks:
        raise RuntimeError("missing DISCORD_WEBHOOK_URL (or DISCORD_WEBHOOK_URLS)")

    msgs = chunk(brief_md)
    ok: list[str] = []
    failed: list[str] = []
    for w in webhooks:
        try:
            _post_one(w, msgs)
            ok.append(w)
        except Exception as e:
            failed.append(w)
            print(f"  WARN Discord webhook failed ({_redact(w)}): {e}", flush=True)
    if not ok:
        raise RuntimeError(f"all {len(webhooks)} Discord webhook(s) failed")
    summary = f"posted {len(msgs)} message(s) to {len(ok)}/{len(webhooks)} Discord webhook(s)"
    return summary + (f" — {len(failed)} FAILED" if failed else "")


if __name__ == "__main__":
    # Standalone: `python post_discord.py brief.md` posts; `--dry` just prints the split.
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]).read_text(encoding="utf-8") if args else sys.stdin.read()
    if "--dry" in sys.argv:
        parts = chunk(src)
        for i, m in enumerate(parts, 1):
            print(f"----- message {i}/{len(parts)} ({len(m)} chars) -----\n{m}\n")
    else:
        print(post(src))
