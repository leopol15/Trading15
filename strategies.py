"""Candidate signal generators. Each returns DataFrame(side, stop_dist) indexed by 15m bar start."""
import numpy as np, pandas as pd
from bt import ema, rsi, atr, htf_to

def _ctx(d15, d1h):
    step = d15.index[1] - d15.index[0]; hstep = d1h.index[1] - d1h.index[0]
    close_t = d15.index + step
    hh = d1h.copy(); hh["e50"] = ema(hh.c, 50); hh["e200"] = ema(hh.c, 200)
    m = htf_to(close_t, hh, ["c", "e50", "e200"], hstep); m.index = d15.index
    return m

def trend_pullback(d15, d1h, p):
    """1h trend (EMA50 vs EMA200) + 15m pullback: RSI dips under lo then recovers, price back above EMA20."""
    m = _ctx(d15, d1h)
    up = (m.e50 > m.e200) & (m.c > m.e50); dn = (m.e50 < m.e200) & (m.c < m.e50)
    r = rsi(d15.c, 14); a = atr(d15, 14); e = ema(d15.c, 20)
    lo, hi = p["rsi_lo"], 100 - p["rsi_lo"]
    dipped = (r.rolling(p["look"]).min() < lo).shift(1).fillna(False).astype(bool)
    popped = (r.rolling(p["look"]).max() > hi).shift(1).fillna(False).astype(bool)
    long_ = up & dipped & (d15.c > e) & (d15.c.shift() <= e.shift())
    short = dn & popped & (d15.c < e) & (d15.c.shift() >= e.shift())
    side = np.where(long_, 1, np.where(short, -1, 0))
    return pd.DataFrame({"side": side, "stop_dist": a * p["atr_sl"]}, index=d15.index)

def breakout(d15, d1h, p):
    """15m Donchian breakout in direction of 1h trend, with volume confirmation."""
    m = _ctx(d15, d1h)
    up = (m.e50 > m.e200); dn = (m.e50 < m.e200)
    n = p["n"]; a = atr(d15, 14)
    hh = d15.h.rolling(n).max().shift(); ll = d15.l.rolling(n).min().shift()
    vol_ok = d15.v > d15.v.rolling(96).mean() * p["vol_x"]
    long_ = up & (d15.c > hh) & vol_ok
    short = dn & (d15.c < ll) & vol_ok
    side = np.where(long_, 1, np.where(short, -1, 0))
    return pd.DataFrame({"side": side, "stop_dist": a * p["atr_sl"]}, index=d15.index)

def mean_rev(d15, d1h, p):
    """Fade 15m Bollinger extremes with RSI exhaustion, only if 1h is not in a strong trend against us."""
    m = _ctx(d15, d1h)
    mid = d15.c.rolling(20).mean(); sd = d15.c.rolling(20).std(); a = atr(d15, 14)
    r = rsi(d15.c, 14)
    lo_band = mid - p["k"] * sd; hi_band = mid + p["k"] * sd
    trend_strength = (m.e50 - m.e200) / m.e200
    long_ = (d15.c < lo_band) & (r < p["rsi"]) & (trend_strength > -p["tf"])
    short = (d15.c > hi_band) & (r > 100 - p["rsi"]) & (trend_strength < p["tf"])
    side = np.where(long_, 1, np.where(short, -1, 0))
    return pd.DataFrame({"side": side, "stop_dist": a * p["atr_sl"]}, index=d15.index)
