"""Backtest engine: signals on 15m, exits simulated on 5m bars, portfolio with risk-based sizing.

Assumptions (conservative):
  * Bybit taker fee 0.055% per side + 0.03% slippage per side
  * funding cost 0.01% of notional per 8h held (charged regardless of side)
  * if SL and TP are both touched in the same 5m candle -> SL is assumed first
  * gaps through SL fill at the candle open
"""
import numpy as np, pandas as pd
from numba import njit

FEE = 0.00055
SLIP = 0.0003
FUND_8H = 0.0001
TZ = "Europe/Sofia"
COINS = ["BTC","ETH","XRP","BNB","SOL","DOGE","ADA","TRX","LINK","AVAX","SUI","XLM","TON","HBAR",
         "BCH","LTC","DOT","UNI","NEAR","APT","AAVE","ETC","HYPE","ICP","FIL","ARB","OP","ATOM"]

_cache = {}
def load(coin):
    if coin not in _cache:
        import os
        parts = [pd.read_parquet(f) for f in (f"data_old/{coin}USDT_5m.parquet", f"data/{coin}USDT_5m.parquet") if os.path.exists(f)]
        df = pd.concat(parts).sort_index()
        df = df[~df.index.duplicated()].asfreq("5min").ffill()
        _cache[coin] = df
    return _cache[coin]

def resample(df, rule):
    r = df.resample(rule, label="left", closed="left").agg({"o":"first","h":"max","l":"min","c":"last","v":"sum"})
    return r.dropna()

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)
def atr(df, n=14):
    pc = df.c.shift()
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def htf_to(base_idx_close, htf, cols, rule):
    """Map completed higher-timeframe values onto base bars (by close time, no look-ahead)."""
    h = htf[cols].copy(); h.index = h.index + pd.Timedelta(rule)   # available at HTF bar close
    return h.reindex(base_idx_close, method="ffill")

@njit(cache=True)
def sim_exit(o, h, l, c, i0, side, sl, tp, imax, be_r, entry, trail):
    """Walk 5m bars from i0 (entry bar, entry at its open). Returns (exit_idx, exit_price, reason).
    be_r>0: once price moves be_r * risk in favour, stop goes to breakeven."""
    risk = abs(entry - sl)
    stop = sl
    ext = entry
    n = len(o)
    if imax >= n: imax = n - 1
    for i in range(i0, imax + 1):
        if side == 1:
            if o[i] <= stop and i > i0: return i, o[i], 0
            if l[i] <= stop: return i, stop, 0
            if h[i] >= tp: return i, tp, 1
            if be_r > 0 and h[i] >= entry + be_r * risk and stop < entry: stop = entry
            if trail > 0:
                if h[i] > ext: ext = h[i]
                if ext - trail > stop: stop = ext - trail
        else:
            if o[i] >= stop and i > i0: return i, o[i], 0
            if h[i] >= stop: return i, stop, 0
            if l[i] <= tp: return i, tp, 1
            if be_r > 0 and l[i] <= entry - be_r * risk and stop > entry: stop = entry
            if trail > 0:
                if l[i] < ext: ext = l[i]
                if ext + trail < stop: stop = ext + trail
    return imax, c[imax], 2

def btc_regime(tf):
    """+1 if BTC 4h close > EMA(50) on 4h (completed bars), else -1."""
    key = ("btcreg", tf)
    if key not in _cache:
        b = resample(load("BTC"), "4h"); e = ema(b.c, 50)
        reg = pd.Series(np.where(b.c > e, 1, -1), index=b.index + pd.Timedelta("4h"))
        base = resample(load("BTC"), tf).index
        _cache[key] = reg.reindex(base + pd.Timedelta(tf), method="ffill").set_axis(base)
    return _cache[key]

def run_coin(coin, signal_fn, p, start=None, end=None, intraday=False, max_hold_h=72,
             day_hours=(8, 22)):
    """Generate trades for one coin. signal_fn(df15, df1h, p) -> DataFrame[side, stop_dist] indexed by 15m bar start."""
    d5 = load(coin)
    tf = p.get("tf", "15min"); htf = {"15min": "1h", "1h": "4h"}[tf]
    if (coin, tf) not in _cache: _cache[(coin, tf)] = (resample(d5, tf), resample(d5, htf))
    d15, d1h = _cache[(coin, tf)]
    sig = signal_fn(d15, d1h, p)
    if p.get("btc_filter") and coin != "BTC":
        bf = btc_regime(tf).reindex(sig.index).fillna(0).values
        sig = sig.copy(); sig.loc[sig.side.values * bf < 0, "side"] = 0
    sig = sig[sig.side != 0]
    t_sig = sig.index + pd.Timedelta(tf)              # decision time = 15m bar close
    if start: m = t_sig >= pd.Timestamp(start, tz="UTC"); sig, t_sig = sig[m], t_sig[m]
    if end:   m = t_sig <  pd.Timestamp(end, tz="UTC");   sig, t_sig = sig[m], t_sig[m]
    loc = t_sig.tz_convert(TZ)
    m = (loc.hour >= day_hours[0]) & (loc.hour < day_hours[1])
    sig, t_sig, loc = sig[m], t_sig[m], loc[m]
    o, h, l, c = (d5[k].values for k in "ohlc")
    idx5 = d5.index
    pos = idx5.searchsorted(t_sig)
    trades = []; busy_until = -1
    for k in range(len(sig)):
        i0 = pos[k]
        if i0 >= len(o) - 1 or i0 <= busy_until: continue
        side = int(sig.side.iat[k]); sd = float(sig.stop_dist.iat[k])
        entry = o[i0]
        sl = entry - side * sd; tp = entry + side * sd * p["tp_r"]
        if intraday:
            lt = loc[k]; close_t = lt.normalize() + pd.Timedelta(hours=day_hours[1])
            imax = idx5.searchsorted(close_t.tz_convert("UTC")) - 1
        else:
            imax = i0 + int(max_hold_h * 12) - 1
        trail = sd * p.get("trail_r", 0.0)
        ei, ep, why = sim_exit(o, h, l, c, i0, side, sl, tp, imax, p.get("be_r", 0.0), entry, trail)
        busy_until = ei
        trades.append((coin, idx5[i0], idx5[min(ei, len(idx5)-1)] + pd.Timedelta("5min"), side, entry, ep, sd / entry, why))
    cols = ["coin","t_in","t_out","side","entry","exit","stop_pct","why"]
    if not trades: return pd.DataFrame(columns=cols)
    return pd.DataFrame(trades, columns=cols)

def portfolio(trades, capital=1000.0, risk=0.01, max_pos=5, max_lev=50, max_notional_x=10):
    """Sequential portfolio simulation with compounding. Risk = fraction of equity lost if SL hit (before costs)."""
    if trades.empty: return trades, pd.Series(dtype=float)
    tr = trades.sort_values("t_in").reset_index(drop=True)
    eq = capital; open_ = []; rows = []
    for r in tr.itertuples():
        # close positions finished before this entry
        still = []
        for op in sorted(open_, key=lambda x: x[0]):
            if op[0] <= r.t_in: eq += op[1]
            else: still.append(op)
        open_ = still
        if len(open_) >= max_pos or eq <= 0: continue
        if any(op[2] == r.coin for op in open_): continue
        notional = min(eq * risk / r.stop_pct, eq * max_notional_x)
        gross = r.side * (r.exit - r.entry) / r.entry
        hold_h = (r.t_out - r.t_in).total_seconds() / 3600
        cost = 2 * (FEE + SLIP) + FUND_8H * hold_h / 8
        pnl = notional * (gross - cost)
        lev = min(max_lev, max(1, int(0.5 / r.stop_pct)))   # liquidation (~1/lev) >= 2x stop distance
        rows.append((*r[1:], notional, lev, notional / lev, pnl, pnl / (eq * risk)))
        open_.append((r.t_out, pnl, r.coin))
    for op in open_: eq += op[1]
    res = pd.DataFrame(rows, columns=list(tr.columns) + ["notional","lev","margin","pnl","R"])
    curve = capital + res.set_index("t_out").sort_index().pnl.cumsum()
    return res, curve

def stats(res, curve, capital=1000.0):
    if res.empty: return dict(trades=0)
    years = (res.t_out.max() - res.t_in.min()).days / 365.25
    final = curve.iloc[-1]
    dd = (curve / curve.cummax() - 1).min()
    wins = res.pnl > 0
    pf = res.pnl[wins].sum() / max(1e-9, -res.pnl[~wins].sum())
    cagr = (final / capital) ** (1 / max(years, 1e-6)) - 1 if final > 0 else -1
    return dict(trades=len(res), win=round(wins.mean()*100, 1), avgR=round(res.R.mean(), 3), PF=round(pf, 2),
                final=round(final, 0), ret_pct=round((final/capital-1)*100, 1), CAGR=round(cagr*100, 1),
                maxDD=round(dd*100, 1), hold_h=round(((res.t_out-res.t_in).dt.total_seconds()/3600).mean(), 1))
