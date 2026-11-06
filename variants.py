"""Sensitivity runs for backtest.py -> results/variants.csv"""
import os
from dataclasses import replace
import pandas as pd
from backtest import Params, load_15m, run, stats

here = os.path.dirname(os.path.abspath(__file__))
df = load_15m(os.path.join(here, "data/raw/BTCUSDT-15m-*.csv"))
base = Params()
variants = {
    "BASE: Michael bands 4H (EMA 12/21)": base,
    "No Michael bands (previous base)": replace(base, band_tf=None),
    "Michael bands 15m": replace(base, band_tf="15min"),
    "Michael bands 1H": replace(base, band_tf="1h"),
    "Michael bands 1D": replace(base, band_tf="1D"),
    "Michael bands 4H, slope mode": replace(base, band_mode="slope"),
    "Michael bands 1H, slope mode": replace(base, band_tf="1h", band_mode="slope"),
    "4H bands + BOS within 2h": replace(base, setup_bars=8),
    "4H bands, longs only": replace(base, sides=("long",)),
    "4H bands, shorts only": replace(base, sides=("short",)),
    "4H bands, no fees": replace(base, fee_pct=0.0),
    "4H bands, force-close at 22:00": replace(base, flat_at_session_end=True),
    "4H bands, 15m pivot strength 3": replace(base, piv_15m=3),
    "4H bands, min R:R 2": replace(base, min_rr=2.0),
}
rows = []
for name, p in variants.items():
    tr, _ = run(df, p)
    rows.append(stats(tr, p, name))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(here, "results/variants.csv"), index=False)
print(out.to_string(index=False))
