"""Sensitivity runs for backtest.py -> results/variants.csv"""
import os
from dataclasses import replace
import pandas as pd
from backtest import Params, load_15m, run, stats

here = os.path.dirname(os.path.abspath(__file__))
df = load_15m(os.path.join(here, "data/raw/BTCUSDT-15m-*.csv"))
base = Params()
variants = {
    "BASE: 15m bands + EMA50/100/200 as S/R": base,
    "15m bands only (no EMA S/R)": replace(base, sr_modes=()),
    "EMA S/R + EMA as take-profit": replace(base, sr_modes=("support", "target")),
    "EMA S/R + EMA as take-profit, min R:R 0.5": replace(base, sr_modes=("support", "target"), min_rr=0.5),
    "EMAs as take-profit only": replace(base, sr_modes=("target",)),
    "EMA S/R: trend200 only": replace(base, sr_modes=("trend200",)),
    "EMA S/R: support + trend200": replace(base, sr_modes=("support", "trend200")),
    "EMA S/R: all three": replace(base, sr_modes=("support", "target", "trend200")),
    "Base, EMAs on 1H": replace(base, sr_tf="1h"),
    "Base, EMAs on 4H": replace(base, sr_tf="4h"),
    "Base, touch tolerance 0.3%": replace(base, sr_tol=0.003),
    "Base, no Michael bands": replace(base, band_tf=None),
    "No bands, no EMA S/R (original rules)": replace(base, band_tf=None, sr_modes=()),
    "Base, longs only": replace(base, sides=("long",)),
    "Base, shorts only": replace(base, sides=("short",)),
    "Base, no fees": replace(base, fee_pct=0.0),
    "Base, BOS within 2h": replace(base, setup_bars=8),
}
rows = []
for name, p in variants.items():
    tr, _ = run(df, p)
    rows.append(stats(tr, p, name))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(here, "results/variants.csv"), index=False)
print(out.to_string(index=False))
