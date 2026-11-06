"""
Pre-registered crypto trend / momentum study (daily, spot, long-only or cash).

Strategies and ALL their parameter values are fixed up front (standard values from the
trend-following literature) and every one is reported - nothing is picked after the fact.

Universe : 12 large coins on Binance spot since 2018 (BTC ETH BNB XRP ADA LTC LINK TRX ETC
           XLM EOS BCH). Includes coins that later lost relevance/delisted (EOS) to limit
           survivorship bias. A coin enters when it has data, and is sold when data ends.
Execution: signal on daily close t, position earns close t -> close t+1.
Costs    : 0.10% fee + 0.05% slippage = 0.15% per unit of turnover.
Periods  : in-sample 2018-2022, out-of-sample 2023-01-01 -> 2026-10-31, and full.

Strategies
  SMA-N     : per coin, long while close > SMA(N), N in {50, 100, 200}.
  DONCH-N   : per coin, buy on close > prior N-day high, sell on close < prior N/2-day low,
              N in {20, 55}.
  TSMOM     : per coin, weight = share of lookbacks {20, 60, 120} with positive return
              (0, 1/3, 2/3, 1).
  XSMOM-L   : weekly, hold top 3 coins by L-day return (only if that return > 0), equal
              weight, L in {14, 28, 56}. Cash otherwise.
  Single-coin strategies are combined into an equal-weight portfolio across available coins.
Benchmarks: BTC buy & hold; equal-weight buy & hold of the universe (daily rebalanced).
"""
import glob, os, sys
import numpy as np
import pandas as pd

COINS = ["BTC", "ETH", "BNB", "XRP", "ADA", "LTC", "LINK", "TRX", "ETC", "XLM", "EOS", "BCH"]
COST = 0.0015
IS_END = "2022-12-31"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "daily")


def load():
    closes, highs, lows = {}, {}, {}
    for c in COINS:
        fs = sorted(glob.glob(os.path.join(DATA, f"{c}USDT-1d-*.csv")))
        if not fs:
            continue
        d = pd.concat([pd.read_csv(f, header=None, usecols=range(5)) for f in fs])
        ts = d[0].astype("int64"); ts = np.where(ts > 10**14, ts // 1000, ts)
        d.index = pd.to_datetime(ts, unit="ms").normalize()
        d = d[~d.index.duplicated()].sort_index()
        closes[c], highs[c], lows[c] = d[4], d[2], d[3]
    C, H, L = (pd.DataFrame(x) for x in (closes, highs, lows))
    idx = pd.date_range(C.index.min(), C.index.max(), freq="D")
    return C.reindex(idx), H.reindex(idx), L.reindex(idx)


# ------------------------------------------------------------------ signals (0..1 per coin)
def sig_sma(C, H, L, n):
    return (C > C.rolling(n).mean()).astype(float)


def sig_donchian(C, H, L, n):
    up = H.rolling(n).max().shift(1); dn = L.rolling(n // 2).min().shift(1)
    s = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    s[C > up] = 1.0; s[C < dn] = 0.0
    return s.ffill().fillna(0.0)


def sig_tsmom(C, H, L, lbs=(20, 60, 120)):
    return sum((C / C.shift(lb) - 1 > 0).astype(float) for lb in lbs) / len(lbs)


def weights_single(sig, C):
    avail = C.notna() & C.shift(1).notna()
    n = avail.sum(axis=1).replace(0, np.nan)
    return (sig.where(avail, 0.0)).div(n, axis=0).fillna(0.0)


def weights_xsmom(C, lb, top=3):
    mom = C / C.shift(lb) - 1
    w = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    last = None
    for i, t in enumerate(C.index):
        if t.weekday() == 0 or last is None:          # rebalance Mondays
            m = mom.loc[t].dropna()
            m = m[m > 0].nlargest(top)
            last = pd.Series(0.0, index=C.columns)
            if len(m):
                last[m.index] = 1.0 / top              # unfilled slots stay in cash
        w.loc[t] = last
    return w.where(C.notna(), 0.0)


# ------------------------------------------------------------------ backtest
def backtest(w, C):
    r = C.pct_change().fillna(0.0)
    w = w.fillna(0.0)
    pos = w.shift(1).fillna(0.0)                       # decided at close t, held t -> t+1
    # weights drift with prices between decisions; turnover approximated on target weights
    turnover = (w - w.shift(1).fillna(0.0)).abs().sum(axis=1)
    ret = (pos * r).sum(axis=1) - turnover * COST
    expo = pos.sum(axis=1)
    return ret, expo, turnover


def metrics(ret, expo=None, turnover=None):
    ret = ret.dropna()
    if len(ret) < 30:
        return {}
    eq = (1 + ret).cumprod()
    yrs = len(ret) / 365
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = ret.std() * np.sqrt(365)
    sharpe = ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    out = {"CAGR_%": 100 * cagr, "vol_%": 100 * vol, "Sharpe": sharpe, "maxDD_%": 100 * dd,
           "Calmar": cagr / -dd if dd < 0 else np.nan}
    if expo is not None:
        out["exposure_%"] = 100 * expo.loc[ret.index].mean()
    if turnover is not None:
        out["turnover/yr"] = turnover.loc[ret.index].sum() / yrs
    return {k: round(v, 2) for k, v in out.items()}


def main():
    C, H, L = load()
    start = C["BTC"].first_valid_index() + pd.Timedelta(days=200)   # warm-up for SMA200
    print(f"Data {C.index[0].date()} -> {C.index[-1].date()}, test starts {start.date()}")

    strats = {}
    for n in (50, 100, 200):
        strats[f"SMA-{n}"] = weights_single(sig_sma(C, H, L, n), C)
    for n in (20, 55):
        strats[f"DONCH-{n}"] = weights_single(sig_donchian(C, H, L, n), C)
    strats["TSMOM(20/60/120)"] = weights_single(sig_tsmom(C, H, L), C)
    for lb in (14, 28, 56):
        strats[f"XSMOM-{lb}"] = weights_xsmom(C, lb)
    strats["BENCH: EW buy&hold"] = weights_single(pd.DataFrame(1.0, index=C.index, columns=C.columns), C)
    btc = pd.DataFrame(0.0, index=C.index, columns=C.columns); btc["BTC"] = 1.0
    strats["BENCH: BTC buy&hold"] = btc
    btc_sma = btc.copy(); btc_sma["BTC"] = sig_sma(C, H, L, 100)["BTC"]
    strats["BTC only, SMA-100"] = btc_sma

    periods = {"IS 2018-2022": (start, pd.Timestamp(IS_END)),
               "OOS 2023-2026": (pd.Timestamp("2023-01-01"), C.index[-1]),
               "FULL": (start, C.index[-1])}
    rows, curves = [], {}
    for name, w in strats.items():
        ret, expo, to = backtest(w, C)
        curves[name] = ret
        for pname, (a, b) in periods.items():
            m = metrics(ret.loc[a:b], expo, to)
            rows.append({"strategy": name, "period": pname, **m})
    res = pd.DataFrame(rows)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    res.to_csv(os.path.join(HERE, "results", "summary.csv"), index=False)
    pd.DataFrame(curves).loc[start:].to_csv(os.path.join(HERE, "results", "daily_returns.csv"))
    pd.set_option("display.width", 200)
    for pname in periods:
        print(f"\n=== {pname}")
        print(res[res.period == pname].drop(columns="period").to_string(index=False))

    # yearly returns
    yr = pd.DataFrame({k: (1 + v.loc[start:]).groupby(v.loc[start:].index.year).prod() - 1
                       for k, v in curves.items()}) * 100
    yr.round(1).to_csv(os.path.join(HERE, "results", "yearly.csv"))
    print("\n=== Yearly return %\n", yr.round(0).T.to_string())


if __name__ == "__main__":
    main()
