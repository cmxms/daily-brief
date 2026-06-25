"""
write_brief.py — turn the gathered data block into the finished brief, via Claude.

Reads playbook.md as the system prompt, hands Claude the data block, and lets it run
a few `web_search` calls (server-side) to add the "why" before writing. Returns the
brief as Markdown. This is the autonomous replacement for a human doing the themed
web pass and writing the brief by hand.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
PLAYBOOK = HERE / "playbook.md"

MODEL = os.environ.get("BRIEF_MODEL", "claude-opus-4-8")
# Server-side web search. Built-in result filtering; no beta header needed. max_uses
# bounds cost (~$0.01/search) — a handful of targeted queries is plenty for a brief.
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}


def write_brief(data_block_md: str) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    system = PLAYBOOK.read_text(encoding="utf-8")
    user = (
        "Here is today's DATA BLOCK (live hard numbers). Read it, run a few targeted "
        "web searches to explain the *why* behind the moves and surface catalysts, then "
        "write today's brief following the playbook exactly. Output ONLY the finished "
        "brief in Markdown, starting with the title line.\n\n"
        f"{data_block_md}"
    )
    messages = [{"role": "user", "content": user}]

    # Server-side web_search runs a sampling loop; if it hits its iteration cap the
    # response comes back with stop_reason "pause_turn" — re-send to resume.
    for _ in range(6):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=system,
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break

    text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(f"empty brief (stop_reason={resp.stop_reason})")
    return text


if __name__ == "__main__":
    # Standalone: read a data block from a file arg or stdin, print the brief.
    src = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else sys.stdin.read()
    print(write_brief(src))
