"""Equity curve + yearly R chart -> results/equity.png"""
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = pd.read_csv("results/trades.csv", parse_dates=["exit_time", "entry_time"])
SURF, INK, INK2, BLUE, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#e6e5e1"
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7), height_ratios=[2, 1], facecolor=SURF)
for a in (a1, a2):
    a.set_facecolor(SURF); a.tick_params(colors=INK2, labelsize=9)
    for s in ("top", "right"): a.spines[s].set_visible(False)
    for s in ("left", "bottom"): a.spines[s].set_color(GRID)
    a.grid(axis="y", color=GRID, lw=0.8); a.set_axisbelow(True)
eq = pd.concat([pd.Series([10000.0], index=[d.entry_time.iloc[0]]), d.set_index("exit_time").equity])
a1.plot(eq.index, eq.values, color=BLUE, lw=2)
a1.axhline(10000, color=INK2, lw=1, ls="--")
a1.set_title("Equity — $10,000 start, 1% risk per trade, 0.04% fee per side", loc="left", color=INK, fontsize=11)
a1.annotate(f"${eq.iloc[-1]:,.0f}", (eq.index[-1], eq.iloc[-1]), xytext=(6, 0), textcoords="offset points", color=INK, fontsize=9, va="center")
y = d.groupby(d.entry_time.dt.year).r.sum()
a2.bar(y.index.astype(str), y.values, color=BLUE, width=0.5)
for x, v in zip(y.index.astype(str), y.values):
    a2.annotate(f"{v:+.1f}R", (x, v), xytext=(0, -12 if v < 0 else 4), textcoords="offset points", ha="center", color=INK, fontsize=9)
a2.axhline(0, color=INK2, lw=1); a2.set_ylim(min(y.min()*1.2, -1), max(y.max()*1.2, 1))
a2.set_title("Net R by year", loc="left", color=INK, fontsize=11)
fig.tight_layout(); fig.savefig("results/equity.png", dpi=150, facecolor=SURF)
