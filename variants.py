"""Sensitivity runs for backtest.py -> results/variants.csv"""
import os
from dataclasses import replace
import pandas as pd
from backtest import Params, load_15m, run, stats

here = os.path.dirname(os.path.abspath(__file__))
df = load_15m(os.path.join(here, "data/raw/BTCUSDT-15m-*.csv"))
base = Params()
variants = {
    "BASE (rules as given)": base,
    "No fees": replace(base, fee_pct=0.0),
    "Hold past 22:00 (no session close)": replace(base, flat_at_session_end=False),
    "No min R:R filter": replace(base, min_rr=0.0),
    "Min R:R 2": replace(base, min_rr=2.0),
    "4H pivot strength 3": replace(base, piv_4h=3),
    "4H pivot strength 5": replace(base, piv_4h=5),
    "15m pivot strength 1": replace(base, piv_15m=1),
    "15m pivot strength 3": replace(base, piv_15m=3),
    "Retest window 4 bars (1h)": replace(base, retest_bars=4),
    "Retest window 16 bars (4h)": replace(base, retest_bars=16),
    "BOS window 8 bars (2h)": replace(base, setup_bars=8),
    "BOS window 32 bars (8h)": replace(base, setup_bars=32),
}
rows = []
for name, p in variants.items():
    tr, _ = run(df, p)
    rows.append(stats(tr, p, name))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(here, "results/variants.csv"), index=False)
print(out.to_string(index=False))
