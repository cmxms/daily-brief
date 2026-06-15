# Daily Brief — Setup (run locally)

A self-contained tool that writes a daily market brief and posts it to your Substack as a
**draft** each weekday morning, on a local schedule. ~$5–8/month of Claude API; everything else
is free tier.

> **Why local (not the cloud)?** Substack's API sits behind Cloudflare, which blocks datacenter
> IPs — so posting from GitHub Actions (or any cloud runner) fails with a bot-challenge. From your
> own machine's IP it works fine. So this runs as a local scheduled task. (The data-gathering and
> AI-writing steps would run anywhere; it's only the Substack post that needs a residential IP.)

## What runs each morning
`run.py` does three steps: **gather** (live data: index futures, macro, sector ETFs, dealer-gamma,
the economic calendar, overnight headlines) → **write** (Claude reads the data, web-searches the
*why*, writes the brief) → **post** (logs into Substack and creates a **draft** you review + publish).

---

## Setup (~20 min, one time)

### 1. Get the keys
| Service | Cost | What for | Where |
|---|---|---|---|
| Anthropic (Claude) API | ~pennies/post | writes the brief | console.anthropic.com → API Keys |
| Tradier | free brokerage acct | live prices + dealer-gamma | tradier.com (no funding needed) |
| Finnhub | free tier | overnight headlines | finnhub.io |

Plus your **Substack** publication URL, login **email**, and **password** (posting logs in and
creates a draft — no "publish via email" needed).

### 2. Install
```
cd daily-brief
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```
Then open `.env` and paste in your keys (it's gitignored — never committed).

### 3. Test by hand first
```
.venv\Scripts\python run.py --gather-only   # just the data — no API cost, confirms sources work
.venv\Scripts\python run.py                 # gather + write, prints the brief to out\. No posting.
.venv\Scripts\python run.py --post          # the whole thing — creates a Substack draft
```
Check `out\<date>.brief.md` (the brief) and your Substack **drafts**. Once a clean draft lands,
schedule it.

### 4. Schedule it (weekday mornings)
```
powershell -ExecutionPolicy Bypass -File register_task.ps1 -Time "06:45"
```
That registers a Windows task **DailyBrief** that runs `run_brief.bat` every weekday at your chosen
time (catches up if the PC was off). Useful commands:
```
Start-ScheduledTask -TaskName DailyBrief                       # run it now to test
Unregister-ScheduledTask -TaskName DailyBrief -Confirm:$false  # remove it
```
Each run appends to `out\run.log`. **The PC must be on at run time** (it's a local task). Pick a
morning time (~6–9 AM ET is ideal — the brief is built on US pre-market data — but any morning works
since you review the draft before publishing).

---

## Notes
- **Draft, not auto-publish.** It creates a draft you approve — safe by default. (Substack login can
  occasionally trip bot-protection; if a run fails to log in, sign into Substack once in a browser,
  then retry.)
- **GEX is prior-session pre-market.** Options don't trade overnight, so the dealer-gamma read
  reflects the prior close; the brief labels it that way.
- **Headlines lag 20–60 min** on Finnhub's free tier — fine for a morning look-back.
- **Glance before publishing.** The writer web-searches for the "why" — eyeball any specific factual
  claim before you hit Publish.
- **Calendar refresh.** `t1_calendar.yaml` (Fed/CPI/jobs dates) needs a 5-minute refresh once a
  quarter from the official sources noted at the top of that file.
- **Model / cost.** Defaults to `claude-opus-4-8` (~$0.35/brief, mostly the web search). Set
  `BRIEF_MODEL=claude-sonnet-4-6` in `.env` to roughly halve it.
