# combined-book-paper — Rs2L combined book, daily paper observation

Paper twin of the intended Rs2,00,000 real deployment, marked **daily** to watch for a month
before (or alongside) going live. Two sleeves:

- **Momentum stocks (~Rs93k)** — 19 names from the 12-1 momentum top-20 (Rs5k slots, POWERINDIA
  skipped: 1 share > slot). Rebalanced on paper on the **last weekday of each month**: sell
  drop-outs from the top-20, buy entrants. No stop-losses — the monthly rank exit is the exit.
- **NIFTY iron condor (1 lot, ~Rs85k margin)** — Aug-2026 cycle from
  [nifty-condor-paper](https://github.com/Jay2597/nifty-condor-paper): SELL 23650PE+24850CE /
  BUY 23350PE+25150CE, credit 89.4 pts, expiry 2026-08-25. **Daily 1.5x-credit stop check**
  (BS-repriced off NIFTY close + India VIX — same approximation as the validated backtest;
  live option prices would differ somewhat). Settles at expiry intrinsic.

**NAV = Rs2,00,000 + stock P&L + condor P&L** (margin/buffer not cash-modeled).
`results/daily_nav.csv` gets one row per trading day via GitHub Actions (17:45 IST);
`results/trades.csv` records paper rebalance orders. Review date: **~Sep 1, 2026** (one month,
one rebalance, one condor expiry observed).

Backtest of this structure over the last 12 months: ~+31-35% (condor sleeve dominant, all of it
from the 5 post-January VIX>=12 cycles; the gate blocked Aug-Jan). Do not extrapolate — the
recent regime was ideal for vol-selling. Paper only; not investment advice.
