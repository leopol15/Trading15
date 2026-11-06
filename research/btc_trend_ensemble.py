"""
FINAL STRATEGY: BTC trend ensemble (daily, spot, long-only or cash)

Exposure = average of 5 standard trend signals on BTC (each 0 or 1, TSMOM 0..1):
  close > SMA50, close > SMA100, close > SMA150, Donchian-20 breakout state, TSMOM(20/60/120)
So exposure moves in steps between 0% and 100% BTC; the rest sits in cash (USDT).
Decide once per day at the daily close (00:00 UTC), trade immediately.
Costs: 0.15% per unit traded (fee + slippage).
"""
import os, numpy as np, pandas as pd
import crypto_trend as ct
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

C, H, L = ct.load()
c = C[["BTC"]]
sigs = [ct.sig_sma(c, H[["BTC"]], L[["BTC"]], n)["BTC"] for n in (50, 100, 150)]
sigs += [ct.sig_donchian(c, H[["BTC"]], L[["BTC"]], 20)["BTC"], ct.sig_tsmom(c, None, None)["BTC"]]
expo = sum(sigs) / len(sigs)
start = c.index[0] + pd.Timedelta(days=200)
r = c["BTC"].pct_change()

def run(delay=1, cost=ct.COST):
    pos = expo.shift(delay)
    ret = (pos * r - expo.diff().abs().shift(delay - 1).fillna(0) * cost).loc[start:]
    return ret.fillna(0)

base, bh = run(), r.loc[start:].fillna(0)
periods = {"IS 2018-07..2022": (start, ct.IS_END), "OOS 2023..2026-10": ("2023-01-01", c.index[-1]), "FULL": (start, c.index[-1])}
rows = []
for name, ret in {"Ensemble": base, "Ensemble, 1-day late": run(2), "Ensemble, 2x costs": run(cost=2 * ct.COST), "BTC buy & hold": bh}.items():
    for p, (a, b) in periods.items():
        rows.append({"strategy": name, "period": p, **ct.metrics(ret.loc[a:b])})
res = pd.DataFrame(rows); res.to_csv(os.path.join(ct.HERE, "results", "btc_ensemble_summary.csv"), index=False)
pd.set_option("display.width", 200); print(res.to_string(index=False))
yr = pd.DataFrame({"Ensemble": (1 + base).groupby(base.index.year).prod() - 1, "BTC B&H": (1 + bh).groupby(bh.index.year).prod() - 1}) * 100
print(yr.round(1).T.to_string()); yr.round(1).to_csv(os.path.join(ct.HERE, "results", "btc_ensemble_yearly.csv"))
print("avg exposure %", round(100 * expo.loc[start:].mean(), 1), " trades/yr (exposure changes)", round((expo.diff().loc[start:] != 0).sum() / (len(base) / 365), 1))
print("current exposure", expo.iloc[-1], "on", expo.index[-1].date())

# chart
SURF, INK, INK2, BLUE, GRAY, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#8a8984", "#e6e5e1"
eq, eqb = (1 + base).cumprod() * 10000, (1 + bh).cumprod() * 10000
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7), height_ratios=[2, 1], facecolor=SURF, sharex=True)
for a in (a1, a2):
    a.set_facecolor(SURF); a.tick_params(colors=INK2, labelsize=9)
    for s in ("top", "right"): a.spines[s].set_visible(False)
    for s in ("left", "bottom"): a.spines[s].set_color(GRID)
    a.grid(axis="y", color=GRID, lw=0.8); a.set_axisbelow(True)
    a.axvline(pd.Timestamp("2023-01-01"), color=INK2, lw=1, ls=":")
a1.plot(eq, color=BLUE, lw=2, label="Trend ensemble"); a1.plot(eqb, color=GRAY, lw=1.5, label="BTC buy & hold")
a1.set_yscale("log"); a1.legend(frameon=False, fontsize=9, loc="upper left")
for s, col in ((eq, BLUE), (eqb, GRAY)):
    a1.annotate(f"${s.iloc[-1]:,.0f}", (s.index[-1], s.iloc[-1]), xytext=(4, 0), textcoords="offset points", fontsize=9, color=INK, va="center")
a1.set_title("Growth of $10,000 (log scale) — dotted line: start of unseen test period", loc="left", fontsize=11, color=INK)
a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
a2.plot(100 * (eq / eq.cummax() - 1), color=BLUE, lw=1.5); a2.plot(100 * (eqb / eqb.cummax() - 1), color=GRAY, lw=1.2)
a2.set_title("Drawdown %", loc="left", fontsize=11, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(ct.HERE, "results", "btc_ensemble.png"), dpi=150, facecolor=SURF)
