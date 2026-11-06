"""
BTCUSDT backtest: 4H liquidity sweep -> 15m BOS -> retest entry,
targets from the previous day's fixed-range volume profile (VAH/VAL)
or the next 4H liquidity pool, trading 10:00-22:00 Plovdiv time.

Rules (as implemented)
----------------------
1. 4H liquidity  : 4H swing highs (buy-side) / swing lows (sell-side), pivot with
                   PIV_4H bars on each side. A level becomes usable only once the
                   pivot is confirmed (no look-ahead) and is removed once swept.
2. Setup         : a 15m candle trades through an active 4H level (sweep).
                   Sweep of a LOW  -> look for LONGS.
                   Sweep of a HIGH -> look for SHORTS.
3. 15m BOS       : after the sweep, a 15m candle CLOSES beyond the most recent
                   confirmed 15m swing point (pivot PIV_15M) in the trade direction.
                   Must happen within SETUP_BARS 15m candles of the sweep.
4. Entry         : limit order on the retest of the broken BOS level, valid for
                   RETEST_BARS candles. Stop = extreme of the sweep move
                   (lowest low for longs / highest high for shorts) +/- a small buffer.
5. Volume profile: fixed-range VP of the previous UTC day (built from 15m candles,
                   volume spread evenly across each candle's range), 70% value area.
6. Exit          : LONG  -> take profit at VAH or at the nearest 4H buy-side liquidity
                            (swing high) above entry, whichever is closer (= hit first).
                   SHORT -> take profit at VAL or the nearest 4H sell-side liquidity,
                            whichever is closer. Stop loss as above.
7. Michael bands: EMA 12/21 on band_tf. A long BOS is only taken while the band is
                   green (EMA12 > EMA21), a short BOS only while it is red.
8. Session       : entries only 10:00-22:00 Europe/Sofia (Plovdiv). Pending orders are
                   cancelled at 22:00. Open trades are NOT closed at 22:00 - they run
                   until TP or SL (set flat_at_session_end=True to force-close).
Conservative fill assumptions: if SL and TP are both inside one candle, SL is assumed;
on the fill candle only the SL is checked.
"""
from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

# ----------------------------------------------------------------- parameters
@dataclass
class Params:
    piv_4h: int = 2              # 4H pivot strength (bars each side)
    piv_15m: int = 2             # 15m pivot strength
    setup_bars: int = 16         # max 15m bars between sweep and BOS (4h)
    retest_bars: int = 8         # max 15m bars to wait for the retest fill (2h)
    sl_buffer_pct: float = 0.0005  # 0.05% beyond the sweep extreme
    min_rr: float = 1.0          # skip trades whose target gives < min_rr
    session_start: int = 10      # Plovdiv local hour
    session_end: int = 22
    flat_at_session_end: bool = False   # True = force-close open trades at 22:00
    va_pct: float = 0.70
    vp_bins: int = 200
    fee_pct: float = 0.0004      # per side (0.04%)
    risk_pct: float = 0.01       # equity risked per trade
    start_equity: float = 10_000.0
    tz: str = "Europe/Sofia"
    sides: tuple = ("long", "short")
    # Michael's EMA bands (EMA fast/slow). Green = fast > slow -> longs only,
    # red = fast < slow -> shorts only. band_tf=None disables the filter.
    band_tf: str | None = "4h"
    band_fast: int = 12
    band_slow: int = 21
    band_mode: str = "cross"     # "cross": colour from fast vs slow
                                 # "slope": green only if both EMAs rise, red only if both fall


# ----------------------------------------------------------------- data
def load_15m(path_glob: str) -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(path_glob)):
        d = pd.read_csv(f, header=None, usecols=range(6),
                        names=["ts", "open", "high", "low", "close", "volume"])
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    ts = df["ts"].astype("int64")
    ts = np.where(ts > 10**14, ts // 1000, ts)  # Binance switched to microseconds in 2025
    df["time"] = pd.to_datetime(ts, unit="ms", utc=True)
    df = df.drop(columns="ts").drop_duplicates("time").set_index("time").sort_index()
    return df


# ----------------------------------------------------------------- volume profile
def value_area(lows, highs, vols, bins, va_pct):
    lo, hi = lows.min(), highs.max()
    if hi <= lo:
        return lo, hi, lo
    edges = np.linspace(lo, hi, bins + 1)
    width = edges[1] - edges[0]
    hist = np.zeros(bins)
    for l, h, v in zip(lows, highs, vols):
        i0 = int(min((l - lo) / width, bins - 1))
        i1 = int(min((h - lo) / width, bins - 1))
        hist[i0:i1 + 1] += v / (i1 - i0 + 1)
    poc = int(hist.argmax())
    total, acc = hist.sum(), hist[poc]
    a = b = poc
    while acc < va_pct * total and (a > 0 or b < bins - 1):
        up = hist[b + 1] if b < bins - 1 else -1
        dn = hist[a - 1] if a > 0 else -1
        if up >= dn:
            b += 1; acc += up
        else:
            a -= 1; acc += dn
    val, vah = edges[a], edges[b + 1]
    poc_px = (edges[poc] + edges[poc + 1]) / 2
    return val, vah, poc_px


def daily_profiles(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    rows = {}
    for day, g in df.groupby(df.index.floor("D")):
        val, vah, poc = value_area(g["low"].values, g["high"].values,
                                   g["volume"].values, p.vp_bins, p.va_pct)
        rows[day] = (val, vah, poc)
    vp = pd.DataFrame.from_dict(rows, orient="index", columns=["val", "vah", "poc"])
    # profile of day D is used on day D+1 (fixed range = previous full day)
    vp.index = vp.index + pd.Timedelta(days=1)
    return vp


# ----------------------------------------------------------------- pivots
def pivots(high, low, n):
    """Return arrays (is_ph, is_pl) marking pivot bars (needs n bars both sides)."""
    L = len(high)
    ph = np.zeros(L, bool); pl = np.zeros(L, bool)
    for i in range(n, L - n):
        win_h = high[i - n:i + n + 1]; win_l = low[i - n:i + n + 1]
        if high[i] == win_h.max() and (win_h == high[i]).sum() == 1:
            ph[i] = True
        if low[i] == win_l.min() and (win_l == low[i]).sum() == 1:
            pl[i] = True
    return ph, pl


def liquidity_4h(df: pd.DataFrame, p: Params):
    """4H swing levels with the time they become known (confirmation time)."""
    h4 = df.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                "close": "last", "volume": "sum"}).dropna()
    ph, pl = pivots(h4["high"].values, h4["low"].values, p.piv_4h)
    idx = h4.index
    conf_delay = pd.Timedelta(hours=4 * (p.piv_4h + 1))  # close of bar i+n
    highs = [(idx[i] + conf_delay, h4["high"].iat[i]) for i in np.where(ph)[0]]
    lows = [(idx[i] + conf_delay, h4["low"].iat[i]) for i in np.where(pl)[0]]
    return h4, highs, lows


# ----------------------------------------------------------------- Michael's EMA bands
def michael_bands(df: pd.DataFrame, p: Params) -> np.ndarray:
    """Band colour known at the CLOSE of each 15m candle: +1 green, -1 red, 0 neutral.
    Uses only completed candles of the band timeframe (no look-ahead)."""
    n = len(df)
    if p.band_tf is None:
        return np.zeros(n)
    tf = pd.Timedelta(p.band_tf)
    if tf == pd.Timedelta("15min"):
        close = df["close"]
    else:
        close = df["close"].resample(p.band_tf).last().dropna()
    fast = close.ewm(span=p.band_fast, adjust=False).mean()
    slow = close.ewm(span=p.band_slow, adjust=False).mean()
    if p.band_mode == "slope":
        up = (fast.diff() > 0) & (slow.diff() > 0)
        dn = (fast.diff() < 0) & (slow.diff() < 0)
        col = pd.Series(np.where(up, 1, np.where(dn, -1, 0)), index=close.index)
    else:
        col = pd.Series(np.sign(fast - slow).values, index=close.index)
    col.index = col.index + tf                      # value is known when the bar closes
    bar_close = df.index + pd.Timedelta("15min")    # when each 15m candle closes
    return col.reindex(bar_close, method="ffill").fillna(0).values


# ----------------------------------------------------------------- engine
@dataclass
class Trade:
    side: str
    sweep_time: pd.Timestamp
    swept_level: float
    bos_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    stop: float
    target: float
    target_src: str
    exit_time: pd.Timestamp = None
    exit: float = None
    reason: str = ""
    r: float = 0.0
    pnl: float = 0.0
    equity: float = 0.0


def run(df: pd.DataFrame, p: Params):
    vp = daily_profiles(df, p)
    _, liq_highs, liq_lows = liquidity_4h(df, p)

    t = df.index
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    n = len(df)
    local_hour = t.tz_convert(p.tz).hour
    in_session = (local_hour >= p.session_start) & (local_hour < p.session_end)
    day_key = t.floor("D")
    vah_arr = vp["vah"].reindex(day_key).values
    val_arr = vp["val"].reindex(day_key).values

    ph15, pl15 = pivots(h, l, p.piv_15m)
    band = michael_bands(df, p)

    active_hi: list[float] = []; active_lo: list[float] = []
    hi_ptr = lo_ptr = 0
    last_sh = last_sl = None          # latest confirmed 15m swing high/low price
    setup = None                      # dict for pending setup
    order = None                      # pending limit order
    pos = None                        # open Trade
    trades: list[Trade] = []
    equity = p.start_equity

    def close_pos(i, px, reason):
        nonlocal pos, equity
        tr = pos
        sign = 1 if tr.side == "long" else -1
        risk_px = abs(tr.entry - tr.stop)
        qty = (equity * p.risk_pct) / risk_px
        gross = sign * (px - tr.entry) * qty
        fees = (tr.entry + px) * qty * p.fee_pct
        tr.pnl = gross - fees
        tr.r = tr.pnl / (equity * p.risk_pct)
        equity += tr.pnl
        tr.exit_time, tr.exit, tr.reason, tr.equity = t[i], px, reason, equity
        trades.append(tr)
        pos = None

    for i in range(n):
        now = t[i]
        # --- activate newly confirmed 4H liquidity (known at bar open time)
        while hi_ptr < len(liq_highs) and liq_highs[hi_ptr][0] <= now:
            active_hi.append(liq_highs[hi_ptr][1]); hi_ptr += 1
        while lo_ptr < len(liq_lows) and liq_lows[lo_ptr][0] <= now:
            active_lo.append(liq_lows[lo_ptr][1]); lo_ptr += 1

        # --- manage open position
        if pos is not None:
            if pos.side == "long":
                if l[i] <= pos.stop:
                    close_pos(i, pos.stop, "SL")
                elif h[i] >= pos.target:
                    close_pos(i, pos.target, "TP " + pos.target_src)
            else:
                if h[i] >= pos.stop:
                    close_pos(i, pos.stop, "SL")
                elif l[i] <= pos.target:
                    close_pos(i, pos.target, "TP " + pos.target_src)
            if pos is not None and p.flat_at_session_end and not in_session[i] \
                    and (i == 0 or in_session[i - 1]):
                close_pos(i, o[i], "Session end")

        # --- pending limit order (retest of BOS level)
        if order is not None and pos is None:
            expired = i > order["expire"] or not in_session[i]
            if order["side"] == "long":
                tp_first = h[i] >= order["target"] and o[i] > order["entry"] and l[i] > order["entry"]
                filled = l[i] <= order["entry"]
            else:
                tp_first = l[i] <= order["target"] and o[i] < order["entry"] and h[i] < order["entry"]
                filled = h[i] >= order["entry"]
            if expired or tp_first:
                order = None
            elif filled:
                fill = order["entry"]
                if order["side"] == "long" and o[i] < fill:
                    fill = o[i]          # gapped through the level: fill at open
                if order["side"] == "short" and o[i] > fill:
                    fill = o[i]
                pos = Trade(order["side"], order["sweep_time"], order["level"], order["bos_time"],
                            now, fill, order["stop"], order["target"], order["src"])
                order = None
                # conservative: on the fill bar only the stop is checked
                if (pos.side == "long" and l[i] <= pos.stop) or \
                   (pos.side == "short" and h[i] >= pos.stop):
                    close_pos(i, pos.stop, "SL")

        # --- sweeps of 4H liquidity (remove swept levels, arm setups)
        swept_lo = [x for x in active_lo if l[i] < x]
        swept_hi = [x for x in active_hi if h[i] > x]
        if swept_lo:
            active_lo = [x for x in active_lo if x not in swept_lo]
        if swept_hi:
            active_hi = [x for x in active_hi if x not in swept_hi]
        if pos is None and order is None:
            if swept_lo and not swept_hi and "long" in p.sides:
                setup = dict(side="long", start=i, level=min(swept_lo), extreme=l[i], time=now)
            elif swept_hi and not swept_lo and "short" in p.sides:
                setup = dict(side="short", start=i, level=max(swept_hi), extreme=h[i], time=now)

        # --- update 15m swing points (pivot at i-n confirmed at close of bar i)
        k = i - p.piv_15m
        if k >= 0:
            if ph15[k]:
                last_sh = h[k]
            if pl15[k]:
                last_sl = l[k]

        # --- look for BOS on an armed setup
        if setup is not None and pos is None and order is None:
            if i - setup["start"] > p.setup_bars:
                setup = None
            else:
                if setup["side"] == "long":
                    setup["extreme"] = min(setup["extreme"], l[i])
                    ref = last_sh   # latest confirmed 15m swing high
                    if i > setup["start"] and ref is not None and c[i] > ref \
                            and (p.band_tf is None or band[i] > 0):
                        order = _make_order(setup, ref, i, now, p, vah_arr, val_arr,
                                            active_hi, active_lo)
                        setup = None
                else:
                    setup["extreme"] = max(setup["extreme"], h[i])
                    ref = last_sl   # latest confirmed 15m swing low
                    if i > setup["start"] and ref is not None and c[i] < ref \
                            and (p.band_tf is None or band[i] < 0):
                        order = _make_order(setup, ref, i, now, p, vah_arr, val_arr,
                                            active_hi, active_lo)
                        setup = None

    if pos is not None:
        close_pos(n - 1, c[-1], "End of data")
    return trades, equity


def _make_order(setup, level, i, now, p, vah_arr, val_arr, active_hi, active_lo):
    side = setup["side"]
    entry = level
    if side == "long":
        stop = setup["extreme"] * (1 - p.sl_buffer_pct)
        cands = []
        if not np.isnan(vah_arr[i]) and vah_arr[i] > entry:
            cands.append((vah_arr[i], "VAH"))
        above = [x for x in active_hi if x > entry]
        if above:
            cands.append((min(above), "4H liq"))
        if not cands:
            return None
        target, src = min(cands)
        risk, reward = entry - stop, target - entry
    else:
        stop = setup["extreme"] * (1 + p.sl_buffer_pct)
        cands = []
        if not np.isnan(val_arr[i]) and val_arr[i] < entry:
            cands.append((val_arr[i], "VAL"))
        below = [x for x in active_lo if x < entry]
        if below:
            cands.append((max(below), "4H liq"))
        if not cands:
            return None
        target, src = max(cands)
        risk, reward = stop - entry, entry - target
    if risk <= 0 or reward / risk < p.min_rr:
        return None
    return dict(side=side, entry=entry, stop=stop, target=target, src=src,
                           expire=i + p.retest_bars, sweep_time=setup["time"],
                           level=setup["level"], bos_time=now)


# ----------------------------------------------------------------- stats
def stats(trades: list[Trade], p: Params, label=""):
    if not trades:
        return {"label": label, "trades": 0}
    d = pd.DataFrame([asdict(x) for x in trades])
    eq = pd.concat([pd.Series([p.start_equity]), d["equity"]], ignore_index=True)
    dd = (eq / eq.cummax() - 1).min()
    wins = d[d.pnl > 0]; losses = d[d.pnl <= 0]
    pf = wins.pnl.sum() / -losses.pnl.sum() if len(losses) and losses.pnl.sum() < 0 else np.inf
    return {
        "label": label,
        "trades": len(d),
        "win_rate_%": round(100 * len(wins) / len(d), 1),
        "avg_R": round(d.r.mean(), 3),
        "total_R": round(d.r.sum(), 1),
        "profit_factor": round(pf, 2),
        "return_%": round(100 * (d.equity.iloc[-1] / p.start_equity - 1), 1),
        "max_dd_%": round(100 * dd, 1),
        "longs": int((d.side == "long").sum()),
        "shorts": int((d.side == "short").sum()),
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    df = load_15m(os.path.join(here, "data/raw/BTCUSDT-15m-*.csv"))
    print(f"Data: {df.index[0]} -> {df.index[-1]}  ({len(df):,} candles)")
    p = Params()
    trades, eq = run(df, p)
    s = stats(trades, p, "base")
    print(s)
    out = pd.DataFrame([asdict(x) for x in trades])
    out.to_csv(os.path.join(here, "results/trades.csv"), index=False)
