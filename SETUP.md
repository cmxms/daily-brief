# Daily Brief — Setup

A self-contained tool that writes a daily market brief and publishes it to Substack on a
free cloud schedule. ~$1–3/month of Claude API; everything else is free tier.

## What runs each morning
`run.py` does three steps: **gather** (live data: index futures, macro, sector ETFs,
dealer-gamma, the economic calendar, overnight headlines) → **write** (Claude reads the data,
web-searches the *why*, writes the brief) → **post** (emails it to Substack as a draft).

---

## One-time setup (~30 min)

### 1. Get the keys
| Service | Cost | What for | Where |
|---|---|---|---|
| Anthropic (Claude) API | ~pennies/post | writes the brief | console.anthropic.com → API Keys |
| Tradier | free brokerage acct | live prices + dealer-gamma | tradier.com (no funding needed) |
| Finnhub | free tier | overnight headlines | finnhub.io |

### 2. Substack account (login-based posting)
Posting uses `python-substack`, which logs into your Substack account and creates a **draft**.
You need three things: your publication URL (e.g. `https://yourname.substack.com`), your
Substack **login email**, and your **password**. No "publish via email" address required.

### 3. Put it on GitHub
1. Create a repo and push this `daily-brief/` folder (or the whole thing).
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**, add:
   `ANTHROPIC_API_KEY`, `TRADIER_API_KEY`, `FINNHUB_API_KEY`, `SUBSTACK_PUBLICATION_URL`,
   `SUBSTACK_EMAIL`, `SUBSTACK_PASSWORD`. (Secrets never live in the code.)
3. The schedule is in `.github/workflows/daily-brief.yml` (`cron: "30 10 * * 1-5"` ≈ 6:30 AM
   ET in summer). Edit the time if you like.
4. **Test it now:** Actions tab → *daily-brief* → **Run workflow**. Check the run log and your
   Substack drafts.

---

## Test locally first (recommended)
```
cd daily-brief
python -m pip install -r requirements.txt
cp .env.example .env          # fill in your keys
python run.py --gather-only   # 1) just the data — no API cost, confirms data sources work
python run.py                 # 2) gather + write, prints the brief, saves to out/. No posting.
python run.py --post          # 3) the whole thing — emails a draft to Substack
```
`out/<date>.brief.md` is the finished brief; `out/<date>.data.md` is the raw data it was built
from. Once the local `--post` lands a clean draft, flip on the GitHub Actions schedule.

---

## Notes
- **Draft, not auto-publish.** `python-substack` creates a draft you approve. That's the safe
  default for the first couple of weeks. (Substack login can occasionally trip bot-protection;
  if a run fails to log in, sign in once in a browser, then retry.)
- **GEX is prior-session pre-market.** Options don't trade overnight, so the dealer-gamma read
  reflects the prior close; the brief labels it that way.
- **Headlines lag 20–60 min** on Finnhub's free tier — fine for a morning look-back.
- **Calendar refresh.** `t1_calendar.yaml` (Fed/CPI/jobs dates) needs a 5-minute refresh once a
  quarter from the official sources noted at the top of that file.
- **Never invent a number.** The writer is instructed to use only fetched figures and to flag
  anything stale; if a data source hiccups it says so rather than guessing.
- **Model.** Defaults to `claude-opus-4-8`. Set the `BRIEF_MODEL` secret to a cheaper model
  (e.g. `claude-sonnet-4-6`) if you want to trim cost.
