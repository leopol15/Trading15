"""Final strategy: 'Afternoon Breakout' — run the full backtest and write results/ (stats, trades, equity chart)."""
import os, pandas as pd, numpy as np, bt, strategies as S
from multiprocessing import Pool
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

PARAMS = dict(tf="1h", n=48, vol_x=2.0, atr_sl=1.5, tp_r=20, trail_r=0.0, btc_filter=False)
HOURS = (14, 22)          # entries only 14:00-22:00 Plovdiv time (Europe/Sofia)
MAX_HOLD_H = 72
CAPITAL, RISK, MAX_POS = 1000.0, 0.0025, 10

def one(c): return bt.run_coin(c, S.breakout, PARAMS, "2021-01-01", "2026-11-01", max_hold_h=MAX_HOLD_H, day_hours=HOURS)

if __name__ == "__main__":
    os.makedirs("results", exist_ok=True)
    with Pool(4) as pool: t = pd.concat([x for x in pool.map(one, bt.COINS) if len(x)])
    out = []
    fig, ax = plt.subplots(2, 1, figsize=(11, 8))
    for i, (start, risk) in enumerate([("2021-01-01", RISK), ("2021-01-01", 0.005), ("2025-01-01", RISK), ("2025-01-01", 0.005)]):
        tt = t[t.t_in >= pd.Timestamp(start, tz="UTC")]
        res, cur = bt.portfolio(tt, CAPITAL, risk, MAX_POS)
        s = bt.stats(res, cur); out.append(dict(start=start, risk_pct=risk * 100, **s))
        res["year"] = res.t_in.dt.year
        yr = res.groupby("year").agg(trades=("pnl", "size"), win_pct=("pnl", lambda x: round((x > 0).mean() * 100, 1)),
                                     pnl_eur=("pnl", "sum"), avgR=("R", "mean")).round(2)
        print(f"\n=== start {start}, risk {risk*100:.2f}%/trade ===\n", yr.to_string())
        if risk == RISK: res.to_csv(f"results/trades_{start[:4]}.csv", index=False)
        ax[0 if start.startswith("2021") else 1].plot(cur.index, cur.values, label=f"risk {risk*100:.2f}%")
    for a, ttl in zip(ax, ["2021-01 → 2026-10 (1000 € старт)", "2025-01 → 2026-10 (1000 € старт)"]):
        a.set_yscale("log"); a.set_title(ttl); a.legend(); a.grid(alpha=.3); a.set_ylabel("EUR")
    plt.tight_layout(); plt.savefig("results/equity.png", dpi=110)
    summary = pd.DataFrame(out); summary.to_csv("results/summary.csv", index=False)
    print("\n", summary.to_string())
