"""mark_daily.py — daily paper mark of the Rs2L combined book (19 momentum stocks +
1-lot NIFTY iron condor).

Runs each trading evening in GitHub Actions:
  * marks the stock sleeve at closes,
  * BS-reprices the condor off NIFTY close + India VIX and applies the 1.5x-credit stop
    on a daily-close basis (same logic as the backtest), settles at expiry intrinsic,
  * on the last weekday of the month, executes the 12-1 momentum rebalance on paper,
  * appends results/daily_nav.csv and results/trades.csv.
Book accounting: NAV = 200,000 + stock P&L + condor P&L (margin not cash-modeled).
"""
import csv, json, math, os
from datetime import date, timedelta
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "book")
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
CAPITAL, N_SLOTS, TAX, DP = 200_000.0, 20, 0.0011, 15.93

def _N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs(S, K, sig, t, call=True):
    if t <= 0 or sig <= 0:
        return max(0.0, (S - K) if call else (K - S))
    d1 = (math.log(S / K) + sig * sig / 2 * t) / (sig * math.sqrt(t))
    d2 = d1 - sig * math.sqrt(t)
    return S * _N(d1) - K * _N(d2) if call else K * _N(-d2) - S * _N(-d1)

stocks = list(csv.DictReader(open(os.path.join(BOOK, "stocks.csv"), newline="")))
condor = json.load(open(os.path.join(BOOK, "condor.json")))
uni = json.load(open(os.path.join(HERE, "universe.json")))["universe"]

tickers = sorted({r["symbol"] + ".NS" for r in stocks} | {s + ".NS" for s in uni}) + ["^NSEI", "^INDIAVIX"]
px = yf.download(tickers, period="15mo", auto_adjust=True, progress=False, group_by="column")["Close"]
today = px.index[-1]
tstr = today.strftime("%Y-%m-%d")

def last(sym):
    s = px.get(sym + ".NS")
    if s is None or s.dropna().empty:
        return None
    return float(s.dropna().iloc[-1])

# ---- stock sleeve ----
stock_val = stock_cost = 0.0
for r in stocks:
    p = last(r["symbol"])
    q = int(r["qty"])
    stock_cost += q * float(r["entry_px"])
    stock_val += q * (p if p is not None else float(r["entry_px"]))
stock_pnl = stock_val - stock_cost

# ---- condor sleeve ----
nifty = float(px["^NSEI"].dropna().iloc[-1])
vix = float(px["^INDIAVIX"].dropna().iloc[-1])
note = ""
if condor["status"] == "open":
    exp = date.fromisoformat(condor["expiry"])
    t_rem = max(( exp - today.date()).days, 0) / 365.0
    sig = vix / 100.0
    cost = (bs(nifty, condor["sp"], sig, t_rem, False) + bs(nifty, condor["sc"], sig, t_rem, True)
            - bs(nifty, condor["lp"], sig, t_rem, False) - bs(nifty, condor["lc"], sig, t_rem, True))
    pts = condor["credit"] - cost
    if today.date() >= exp:
        intr = (max(0.0, condor["sp"] - nifty) + max(0.0, nifty - condor["sc"])
                - max(0.0, condor["lp"] - nifty) - max(0.0, nifty - condor["lc"]))
        condor.update(status="closed", realized_pts=round(condor["credit"] - intr, 1),
                      exit_date=tstr, exit_reason="expiry")
        pts = condor["realized_pts"]
        note = f"CONDOR SETTLED at expiry: {pts:+.1f} pts"
    elif condor["stop_mult"] and cost >= condor["stop_mult"] * condor["credit"]:
        condor.update(status="closed", realized_pts=round(pts, 1), exit_date=tstr,
                      exit_reason=f"stop {condor['stop_mult']}x")
        note = f"CONDOR STOPPED: cost {cost:.1f} >= {condor['stop_mult']}x credit -> {pts:+.1f} pts"
    json.dump(condor, open(os.path.join(BOOK, "condor.json"), "w"), indent=2)
else:
    pts = condor["realized_pts"] or 0.0
condor_rs = pts * condor["lot"]

# ---- month-end paper rebalance of the stock sleeve ----
nxt = today.date() + timedelta(days=1)
while nxt.weekday() >= 5:
    nxt += timedelta(days=1)
if nxt.month != today.month:
    mom = (px.iloc[-1 - 21] / px.iloc[-1 - 251] - 1).dropna()
    mom = mom[[c for c in mom.index if c.endswith(".NS")]]
    mom.index = [c[:-3] for c in mom.index]
    top = list(mom[[s in uni for s in mom.index]].nlargest(N_SLOTS).index)
    cash_est = CAPITAL - 107_000 - stock_cost  # buffer bookkeeping only
    held = {r["symbol"]: r for r in stocks}
    trades = []
    for s in [s for s in held if s not in top]:
        p = last(s) or float(held[s]["entry_px"])
        trades.append([tstr, "SELL", s, held[s]["qty"], f"{p:.2f}",
                       f"{(p/float(held[s]['entry_px'])-1)*100:.2f}"])
        del held[s]
    eq_sleeve = sum(int(r["qty"]) * (last(sym) or float(r["entry_px"])) for sym, r in held.items())
    slot = max((eq_sleeve + stock_pnl * 0) / max(len(held), 1), 5000.0)
    for s in top:
        if s not in held:
            p = last(s)
            if p and p <= slot * 1.25:
                q = max(1, round(5000 / p))
                held[s] = dict(symbol=s, qty=str(q), entry_px=f"{p:.2f}", entry_date=tstr)
                trades.append([tstr, "BUY", s, q, f"{p:.2f}", ""])
    with open(os.path.join(BOOK, "stocks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "qty", "entry_px", "entry_date"])
        w.writeheader()
        for r in held.values():
            w.writerow(r)
    if trades:
        newf = not os.path.exists(os.path.join(RES, "trades.csv"))
        with open(os.path.join(RES, "trades.csv"), "a", newline="") as f:
            w = csv.writer(f)
            if newf:
                w.writerow(["date", "side", "symbol", "qty", "px", "ret_pct"])
            w.writerows(trades)
        note = (note + " | " if note else "") + f"REBALANCE: {len(trades)} paper orders"

nav = CAPITAL + stock_pnl + condor_rs
navf = os.path.join(RES, "daily_nav.csv")
newf = not os.path.exists(navf)
with open(navf, "a", newline="") as f:
    w = csv.writer(f)
    if newf:
        w.writerow(["date", "stocks_value", "stocks_pnl", "condor_pts", "condor_rs",
                    "nav", "nifty", "vix", "condor_status", "note"])
    w.writerow([tstr, f"{stock_val:.0f}", f"{stock_pnl:+.0f}", f"{pts:+.1f}",
                f"{condor_rs:+.0f}", f"{nav:.0f}", f"{nifty:.1f}", f"{vix:.2f}",
                condor["status"], note])
print(f"{tstr}: NAV Rs{nav:,.0f} (stocks {stock_pnl:+,.0f}, condor {condor_rs:+,.0f} "
      f"[{pts:+.1f}pts, {condor['status']}]) NIFTY {nifty:.0f} VIX {vix:.1f} {note}")
