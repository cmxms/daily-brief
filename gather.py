"""
gather.py — the deterministic data layer for the daily Substack brief.

Pulls every HARD NUMBER from live, cloud-reachable sources so the brief is never
built on the model's memory:
  - index futures + oil + macro (yields/VIX) + sector ETFs   -> yfinance (free)
  - dealer gamma (GEX) for SPY + QQQ                          -> Tradier live chain (we own the math)
  - economic-event gate                                       -> bundled t1_calendar.yaml
  - overnight headlines                                       -> Finnhub (free tier)

It writes a structured data block (JSON + a readable markdown dump). The writer
(write_brief.py) reads that block, web-searches the "why", and writes the brief.

SELF-CONTAINED: no imports from sibling projects, no local database. Credentials come
from environment variables (GitHub Actions secrets) or a local .env file in this folder.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import requests
import yaml
import yfinance as yf

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = None

# Windows consoles default to cp1252 and choke on the ★/→/— glyphs — force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
T1_CALENDAR = HERE / "t1_calendar.yaml"
OUT_DIR = HERE / "out"


# --------------------------------------------------------------------------- #
# env: real env vars win (GitHub Actions secrets); else fall back to ./.env
# --------------------------------------------------------------------------- #
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


_load_dotenv()


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
INDEX_FUTURES = {"ES": "ES=F", "YM": "YM=F", "NQ": "NQ=F", "RTY": "RTY=F"}
INDEX_LABEL = {"ES": "S&P 500", "YM": "Dow", "NQ": "Nasdaq-100", "RTY": "Russell 2000"}
OIL = ("CL=F", "WTI crude")
RATES_VOL = {"^TNX": "10Y yield", "^TYX": "30Y yield", "^FVX": "5Y yield",
             "^VIX": "VIX (30d)", "^VIX9D": "VIX9D (9d)"}
SECTOR_ETFS = {"XLK": "Technology", "XLC": "Communications", "XLY": "Consumer Disc",
               "XLP": "Consumer Staples", "XLE": "Energy", "XLF": "Financials",
               "XLV": "Health Care", "XLI": "Industrials", "XLB": "Materials",
               "XLRE": "Real Estate", "XLU": "Utilities"}
THEME_ETFS = {"SMH": "Semis", "IGV": "Software", "ARKK": "Growth/spec"}
ROTATION_BENCH = "SPY"
GEX_SYMBOLS = ("SPY", "QQQ")

TRUSTED_SOURCES = {"reuters", "bloomberg", "cnbc", "the wall street journal", "wsj",
                   "financial times", "ft", "associated press", "ap", "barrons", "barron's",
                   "marketwatch", "the new york times", "nyt", "axios", "the economist"}
THEME_KEYWORDS = ["ai", "artificial intelligence", "nvidia", "nvda", "chip", "semiconductor",
                  "broadcom", "avgo", "fed", "rate", "cpi", "inflation", "powell", "jobs",
                  "payroll", "oil", "crude", "iran", "hormuz", "tariff", "tech", "nasdaq"]


# --------------------------------------------------------------------------- #
# yfinance helpers (index / macro / sectors)
# --------------------------------------------------------------------------- #
def _close_series(h):
    c = h["Close"]
    c = c.iloc[:, 0] if hasattr(c, "columns") else c
    return c.dropna()


def pull_daily(ticker: str) -> dict:
    try:
        h = yf.download(ticker, period="7d", interval="1d", progress=False, auto_adjust=False)
        if h.empty:
            return {"error": "no data"}
        c = _close_series(h)
        hi, lo = h["High"], h["Low"]
        hi = hi.iloc[:, 0] if hasattr(hi, "columns") else hi
        lo = lo.iloc[:, 0] if hasattr(lo, "columns") else lo
        last = float(c.iloc[-1])
        prev = float(c.iloc[-2]) if len(c) > 1 else None
        return {
            "last": round(last, 3),
            "prev_close": round(prev, 3) if prev else None,
            "chg": round(last - prev, 3) if prev else None,
            "chg_pct": round(100 * (last - prev) / prev, 2) if prev else None,
            "last_date": str(c.index[-1].date()),
            "last_range": [round(float(lo.iloc[-1]), 3), round(float(hi.iloc[-1]), 3)],
            "recent_closes": [round(float(x), 3) for x in c.iloc[-6:]],
        }
    except Exception as e:
        return {"error": repr(e)}


def macro_pulse() -> dict:
    out = {}
    for t, lbl in RATES_VOL.items():
        d = pull_daily(t)
        d["label"] = lbl
        out[t] = d
    try:
        v, v9 = out["^VIX"]["last"], out["^VIX9D"]["last"]
        out["term_structure"] = {
            "vix": v, "vix9d": v9, "spread_9d_minus_30d": round(v9 - v, 2),
            "state": "BACKWARDATION (acute near-term fear)" if v9 > v else "contango (normal)",
        }
    except Exception:
        pass
    return out


def sector_rotation() -> dict:
    def ret5(d):
        cl = d.get("recent_closes") or []
        return round(100 * (cl[-1] / cl[0] - 1), 2) if len(cl) >= 2 and cl[0] else None

    bench = pull_daily(ROTATION_BENCH)
    b1, b5 = bench.get("chg_pct"), ret5(bench)
    rows = []
    for t, lbl in {**SECTOR_ETFS, **THEME_ETFS}.items():
        d = pull_daily(t)
        if "error" in d or d.get("chg_pct") is None:
            continue
        r1, r5 = d["chg_pct"], ret5(d)
        rows.append({"etf": t, "label": lbl, "chg_1d": r1, "chg_5d": r5,
                     "rel_1d": round(r1 - b1, 2) if b1 is not None else None,
                     "rel_5d": round(r5 - b5, 2) if (r5 is not None and b5 is not None) else None,
                     "is_theme": t in THEME_ETFS})
    rows.sort(key=lambda x: (x["rel_5d"] if x["rel_5d"] is not None else (x["rel_1d"] or 0)),
              reverse=True)
    return {"bench": {"etf": ROTATION_BENCH, "chg_1d": b1, "chg_5d": b5}, "ranked": rows}


def index_recap() -> dict:
    idx = {k: {**pull_daily(v), "label": INDEX_LABEL[k]} for k, v in INDEX_FUTURES.items()}
    idx[OIL[0]] = {**pull_daily(OIL[0]), "label": OIL[1]}
    idx["divergence_pct"] = {k: idx[k].get("chg_pct") for k in INDEX_FUTURES}
    return idx


# --------------------------------------------------------------------------- #
# Tradier live GEX (dealer gamma) — ported from the flow study; we own the math
# --------------------------------------------------------------------------- #
def _tradier_get(endpoint: str, params: dict):
    tok = os.environ.get("TRADIER_API_KEY", "").strip()
    if not tok:
        raise RuntimeError("no TRADIER_API_KEY")
    r = requests.get(f"https://api.tradier.com/v1{endpoint}",
                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                     params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _quote(symbol: str):
    q = (_tradier_get("/markets/quotes", {"symbols": symbol}).get("quotes") or {}).get("quote")
    return q[0] if isinstance(q, list) else q


def _expirations(symbol: str):
    e = (_tradier_get("/markets/options/expirations", {"symbol": symbol}).get("expirations") or {}).get("date", [])
    return [e] if isinstance(e, str) else (e or [])


def _chain(symbol: str, expiration: str):
    o = (_tradier_get("/markets/options/chains",
                      {"symbol": symbol, "expiration": expiration, "greeks": "true"}).get("options") or {}).get("option", [])
    return [o] if isinstance(o, dict) else (o or [])


def compute_gex(symbol: str, expirations, spot=None) -> dict:
    """Net dealer GEX by strike: gamma*OI*100*spot^2*0.01, calls +, puts -.
    flip = cumulative-GEX zero-cross strike; call/put wall = max/min strike."""
    if spot is None:
        q = _quote(symbol)
        spot = float(q.get("last") or q.get("close"))
    by_strike = {}
    for exp in expirations:
        for o in _chain(symbol, exp):
            g = (o.get("greeks") or {}).get("gamma")
            oi, strike, otype = o.get("open_interest"), o.get("strike"), o.get("option_type")
            if g is None or oi is None or strike is None or otype not in ("call", "put"):
                continue
            gex = float(g) * float(oi) * 100.0 * (spot ** 2) * 0.01
            by_strike[strike] = by_strike.get(strike, 0.0) + (-gex if otype == "put" else gex)
    total = sum(by_strike.values())
    flip, cum, prev = None, 0.0, None
    for k in sorted(by_strike):
        new = cum + by_strike[k]
        if prev is not None and (cum < 0 <= new or cum > 0 >= new):
            flip = k
        cum, prev = new, k
    return {"spot": round(spot, 2), "total_gex": total,
            "regime": "positive" if total > 0 else "negative",
            "flip": flip,
            "call_wall": max(by_strike, key=by_strike.get) if by_strike else None,
            "put_wall": min(by_strike, key=by_strike.get) if by_strike else None}


def gex_live(today: dt.date) -> dict:
    """Front-dated GEX for SPY+QQQ from the live chain. NOTE: pre-market this reflects
    the PRIOR session's IV/greeks (options don't trade overnight) — label it as such."""
    out = {}
    for sym in GEX_SYMBOLS:
        try:
            exps = _expirations(sym)
            # nearest expirations within ~8 days drive intraday dealer gamma
            near = [e for e in exps if 0 <= (dt.date.fromisoformat(e) - today).days <= 8][:3]
            if not near:
                near = exps[:2]
            out[sym] = compute_gex(sym, near) | {"expirations": near}
        except Exception as e:
            out[sym] = {"error": repr(e)}
    return out


# --------------------------------------------------------------------------- #
# Event gate + Finnhub
# --------------------------------------------------------------------------- #
def event_gate(today: dt.date, horizon_days: int = 21) -> dict:
    if not T1_CALENDAR.exists():
        return {"error": "no t1 calendar"}
    cal = yaml.safe_load(T1_CALENDAR.read_text(encoding="utf-8"))
    events = []
    for e in cal.get("events", []):
        d = e["date"] if isinstance(e["date"], dt.date) else dt.date.fromisoformat(str(e["date"]))
        delta = (d - today).days
        if 0 <= delta <= horizon_days:
            events.append({"name": e["name"], "date": str(d), "time_et": e.get("time_et"),
                           "days_away": delta, "verified": e.get("verified")})
    events.sort(key=lambda x: x["days_away"])
    return {"today_is_t1": any(e["days_away"] == 0 for e in events),
            "today_events": [e for e in events if e["days_away"] == 0],
            "upcoming": events}


def finnhub_news() -> dict:
    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not key:
        return {"error": "no FINNHUB_API_KEY (headlines skipped)"}
    out = {"general": [], "themed": []}
    try:
        r = requests.get("https://finnhub.io/api/v1/news",
                         params={"category": "general", "token": key}, timeout=25)
        out["status"] = r.status_code
        rows, seen = [], set()
        for x in (r.json() if r.status_code == 200 else []):
            hl = (x.get("headline") or "").strip()
            if not hl or hl in seen:
                continue
            seen.add(hl)
            rows.append({"headline": hl, "source": x.get("source", ""),
                         "dt": (dt.datetime.fromtimestamp(x["datetime"], dt.timezone.utc).isoformat()
                                if x.get("datetime") else None),
                         "trusted": x.get("source", "").lower() in TRUSTED_SOURCES})
        rows.sort(key=lambda x: x["dt"] or "", reverse=True)
        rows.sort(key=lambda x: not x["trusted"])
        out["general"] = rows[:14]
        out["themed"] = [x for x in rows if any(k in x["headline"].lower() for k in THEME_KEYWORDS)][:12]
    except Exception as e:
        out["error"] = repr(e)
    return out


# --------------------------------------------------------------------------- #
# Assemble + render
# --------------------------------------------------------------------------- #
def _today_et() -> dt.date:
    now = dt.datetime.now(_ET) if _ET else dt.datetime.now()
    return now.date()


def gather(today: dt.date | None = None) -> dict:
    today = today or _today_et()
    return {"as_of": dt.datetime.now().isoformat(timespec="seconds"),
            "date": str(today),
            "event_gate": event_gate(today),
            "index_recap": index_recap(),
            "macro_pulse": macro_pulse(),
            "sector_rotation": sector_rotation(),
            "gex": gex_live(today),
            "finnhub": finnhub_news()}


def render_md(d: dict) -> str:
    L = [f"# BRIEF DATA BLOCK — {d['date']}  (gathered {d['as_of']})", ""]
    eg = d["event_gate"]
    L.append("## Event gate")
    L.append(f"- today_is_t1: **{eg.get('today_is_t1')}**")
    for e in eg.get("upcoming", [])[:6]:
        L.append(f"  - +{e['days_away']}d  {e['date']}  {e['name']} {e.get('time_et') or ''}"
                 f"{'' if e.get('verified') else '  (unverified)'}")

    L.append("\n## Index recap (daily close-to-close)")
    ir = d["index_recap"]
    for k in ["ES", "YM", "NQ", "RTY", "CL=F"]:
        v = ir.get(k, {})
        if "error" in v:
            L.append(f"- {k}: ERROR {v['error']}"); continue
        L.append(f"- {v.get('label', k)} ({k}): {v.get('last')}  {v.get('chg_pct')}%  "
                 f"range {v.get('last_range')}  [{v.get('last_date')}]")
    L.append(f"- divergence %: {ir.get('divergence_pct')}")

    L.append("\n## Macro pulse (LIVE — yfinance)")
    mp = d["macro_pulse"]
    for t in ["^TNX", "^TYX", "^FVX", "^VIX", "^VIX9D"]:
        v = mp.get(t, {})
        if "error" not in v:
            L.append(f"- {v.get('label')} ({t}): {v.get('last')}  chg {v.get('chg')}  [{v.get('last_date')}]")
    ts = mp.get("term_structure")
    if ts:
        L.append(f"- TERM STRUCTURE: VIX9D {ts['vix9d']} vs VIX {ts['vix']} "
                 f"(spread {ts['spread_9d_minus_30d']}) -> {ts['state']}")

    sr = d.get("sector_rotation", {})
    if sr.get("ranked"):
        f = lambda x: f"{x:+.2f}" if isinstance(x, (int, float)) else " na "
        b = sr["bench"]
        L.append("\n## Sector rotation (ETF rel-perf vs SPY — LIVE yfinance)")
        L.append(f"- bench {b['etf']}: 1d {f(b['chg_1d'])}%  5d {f(b['chg_5d'])}%")
        rk = sr["ranked"]
        L.append("- LEADERS (rel 5d, + = rotating IN):")
        for r in rk[:4]:
            th = " [theme]" if r["is_theme"] else ""
            L.append(f"    {r['etf']:4s} {r['label']:15s} 1d {f(r['chg_1d'])}% (rel {f(r['rel_1d'])})  "
                     f"5d {f(r['chg_5d'])}% (rel {f(r['rel_5d'])}){th}")
        L.append("- LAGGARDS (rel 5d, - = rotating OUT):")
        for r in rk[-4:]:
            th = " [theme]" if r["is_theme"] else ""
            L.append(f"    {r['etf']:4s} {r['label']:15s} 1d {f(r['chg_1d'])}% (rel {f(r['rel_1d'])})  "
                     f"5d {f(r['chg_5d'])}% (rel {f(r['rel_5d'])}){th}")
        themes = [r for r in rk if r["is_theme"]]
        if themes:
            L.append("- THEME proxies: " + " · ".join(f"{r['etf']} rel5d {f(r['rel_5d'])}" for r in themes))

    L.append("\n## GEX (dealer gamma — Tradier live chain; PRIOR-SESSION greeks pre-market)")
    for sym, v in d["gex"].items():
        if "error" in v:
            L.append(f"- {sym}: ERROR {v['error']}"); continue
        L.append(f"- {sym}: spot {v['spot']}, regime **{v['regime']}**, gamma-flip {v['flip']}, "
                 f"call-wall {v['call_wall']}, put-wall {v['put_wall']}  (exp {v.get('expirations')})")

    L.append("\n## Finnhub headlines")
    fh = d["finnhub"]
    if "error" in fh:
        L.append(f"- {fh['error']}")
    else:
        L.append(f"- status: {fh.get('status')}")
        L.append("- GENERAL (trusted-first):")
        for x in fh.get("general", [])[:12]:
            L.append(f"  {'★' if x['trusted'] else ' '} [{x['source']}] {x['headline']}  ({x['dt']})")
        L.append("- THEMED:")
        for x in fh.get("themed", [])[:10]:
            L.append(f"  • [{x['source']}] {x['headline']}")
    return "\n".join(L)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    d = gather()
    (OUT_DIR / f"{d['date']}.json").write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
    md = render_md(d)
    (OUT_DIR / f"{d['date']}.data.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\n[gather] wrote out/{d['date']}.json + out/{d['date']}.data.md")


if __name__ == "__main__":
    main()
