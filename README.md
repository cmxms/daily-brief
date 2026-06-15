# Daily Market Brief — Automated Generator

A self-contained tool that writes a polished daily market brief every morning and hands
it to you ready to post (e.g., to Substack). It runs itself on a free schedule in the
cloud — no server to maintain, nothing running on anyone else's machine. The only thing
it costs you is a few cents of AI usage per post.

This README is for you to **review before we set it up** — it covers what it does, what
you'll need, what it costs, and how it runs.

---

## What it produces

A clean, reader-friendly brief each market morning, in these sections:

- **TL;DR** — the 3–4 things that matter today, for skimmers.
- **Last 24h — what happened & why** — the overnight catalysts (not just *that* the
  market moved, but *why*).
- **Divergence** — how the four big index futures (S&P / Dow / Nasdaq / Russell) are
  moving relative to each other (all-aligned = trend risk; narrow = fragile move).
- **Sector rotation** ⭐ — the 11 sector ETFs plus semis/software/growth, ranked by how
  they're performing *relative to the S&P*, with a plain-English read of what's rotating
  in vs out and what that risk-on/risk-off shift means. (This is the section readers tend
  to like most — it often catches a defensive rotation the headline index number hides.)
- **Macro pulse** — yields, VIX, the VIX term structure, and oil, framed as *moves*, not
  just levels.
- **🚨 Event gate** — the high-impact economic events today and this week (Fed, CPI,
  jobs) so readers know when the calendar is loaded.
- **Regime read** — what dealer gamma + volatility imply about whether it's a
  range-bound or trend day, and where fades vs breakouts tend to get punished.

Every number is pulled live from a real data source — the tool is built to **never invent
a figure**, and to flag anything stale rather than imply it's fresh.

---

## What you'll need

| Service | Cost | What it's for | Sign-up |
|---|---|---|---|
| **Anthropic (Claude) API** | ~pennies/post | Writes the brief | console.anthropic.com |
| **Tradier** | Free (brokerage acct) | Live prices + dealer-gamma (GEX) | tradier.com |
| **Finnhub** | Free tier | Overnight headlines | finnhub.io |
| **FRED** | Free | Macro data (optional) | fred.stlouisfed.org |
| **GitHub** | Free | Hosts + schedules the job | github.com |

**Realistic monthly cost: about $1–3 of Claude API, and nothing else.** Everything else
runs on free tiers, and the cloud scheduler (GitHub Actions) is free for this. Each brief
is a small request, so you're paying cents per post.

The one "open an account" step beyond getting API keys is a **free Tradier brokerage
account** — that's what powers the live gamma/GEX read and gives reliable price data from
the cloud. (You don't have to fund or trade anything; it's just for the data API.)

---

## How it works

Three small steps run in sequence each morning:

1. **Gather** — pulls the day's live data: index futures, the sector ETFs, yields/VIX/oil,
   today's economic calendar, a live dealer-gamma snapshot from Tradier, and overnight
   headlines from Finnhub.
2. **Write** — sends that data to Claude with a detailed playbook (the section template,
   the "translate the tickers and tell the story" instructions, and the hard rule never to
   make up a number). Claude also runs a few targeted web searches to add the *why* behind
   the moves, then writes the finished brief.
3. **Post** — hands you the finished brief to publish.

It's scheduled with **GitHub Actions** — a free, built-in scheduler. You commit the code
once, paste your API keys into GitHub's encrypted "Secrets," set the run time, and it fires
on its own every weekday morning. There's no server to keep alive and nothing on anyone's
laptop.

---

## Setup (one-time, ~30 minutes)

1. **Create the repo** from the package you'll be given (or fork/clone it).
2. **Get your API keys** from the five services above.
3. **Add them as GitHub repo Secrets** (Settings → Secrets and variables → Actions). The
   workflow reads them from there — they never live in the code.
4. **Set your run time** in the workflow file (a one-line cron schedule — e.g., 6:00 AM ET,
   weekdays).
5. **Wire up posting** (see next section).
6. **Test it** — trigger the workflow manually once from the Actions tab and check the
   brief it produces.

That's it. After that it runs itself.

---

## The Substack posting piece (the one part that needs your call)

Substack doesn't have a clean official "post via API" button, so this is the only step with
real choices. The brief is produced as plain Markdown; you pick how it lands:

- **Email-to-publish** — Substack can publish from a special email address. Simplest, but
  formatting is basic.
- **`python-substack`** — an open-source library that drives Substack's private API
  (logs in with your account) to create a draft or publish. More control; a little more setup.
- **Draft only** — have it create the draft and you hit "publish" yourself after a glance.
  A nice middle ground if you want a human eyeball before it goes out.

I'd suggest starting with **draft-only** so you can sanity-check the first couple weeks,
then flip to full auto once you trust it. We can set up whichever you prefer.

---

## It's yours to tweak

The whole thing is configurable — none of it is locked down:

- **Sections** — add, remove, or reorder them.
- **Tickers** — swap in the sectors/ETFs/indices you care about.
- **Voice & length** — the playbook is just a text file; edit it to sound like you and to
  hit whatever length fits your Substack.
- **Schedule** — change the cron time, or add a weekend "week ahead" edition.

---

## Things to know (so nothing surprises you)

- **Headlines lag ~20–60 min** on Finnhub's free tier. That's fine for a morning
  look-back; it's not built for real-time trading.
- **The economic calendar is a static file** that needs a quick refresh once a quarter
  (the Fed/BLS publish their dates) — a 5-minute task, and there's a note in the repo for it.
- **Pinned dependencies** — the package locks library versions so a surprise update doesn't
  silently break your 6 AM job.
- **Fails safely** — if a data source hiccups, the brief says "data unavailable" for that
  section rather than guessing. It will never publish a made-up number.
- **Not financial advice** — the brief is situational awareness. Worth ending each post with
  a one-line disclaimer (the template already does).

---

## What's included vs. what you provide

**Included in the package:** the data-gathering script, the brief-writing script, the
playbook (section template + voice), the economic-calendar file, the GitHub Actions schedule,
and a setup guide.

**You provide:** your own API keys (all free except the few cents of Claude), and your
Substack posting preference.

---

## Status

A couple of pieces are being finalized before handoff — the live data-gatherer is being
adapted to run fully in the cloud (no local dependencies), and the auto-writer step is being
wired to the Claude API. Once those are in, the package above is everything you need. Review
this and let me know if the sections/cost/setup work for you, and whether you want
draft-only or full-auto posting to start.
