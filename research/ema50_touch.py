"""
EMA-50 first-touch strategy (daily, long only)

Entry (all conditions known at yesterday's close, entry intraday today):
  1. Michael's EMA bands green : EMA12 > EMA21
  2. EMAs stacked              : EMA50 > EMA100 > EMA200
  3. Price came from above     : yesterday's close > EMA50
  4. Today's low touches EMA50 (yesterday's EMA50 value) -> buy at that price
     (at the open if the day opens below it)
  5. Only the FIRST touch since the bands turned green. Next trade needs the bands to turn
     red and green again.
Exit (main): bands turn red (EMA12 < EMA21 on a daily close) -> sell at that close.
Alternative exits tested for comparison only.
Costs: 0.15% per side (fee + slippage). 100% of equity per trade, no leverage.
"""
import os, sys
import numpy as np, pandas as pd
import crypto_trend as ct
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

COST = 0.0015


def load_ohlc(coin):
    import glob
    fs = sorted(glob.glob(os.path.join(ct.DATA, f"{coin}USDT-1d-*.csv")))
    d = pd.concat([pd.read_csv(f, header=None, usecols=range(5)) for f in fs])
    ts = d[0].astype("int64"); ts = np.where(ts > 10**14, ts // 1000, ts)
    d.index = pd.to_datetime(ts, unit="ms").normalize()
    d = d[~d.index.duplicated()].sort_index()
    d.columns = ["ts", "open", "high", "low", "close"]
    return d.drop(columns="ts")


def run(d, exit_rule="bands_red"):
    c = d["close"]
    e = {n: c.ewm(span=n, adjust=False).mean() for n in (12, 21, 50, 100, 200)}
    green = e[12] > e[21]
    o, h, l, cl = d["open"].values, d["high"].values, d["low"].values, c.values
    g = green.values; e50, e100, e200 = e[50].values, e[100].values, e[200].values
    idx = d.index
    trades, pos, used = [], None, False
    for i in range(201, len(d)):              # skip EMA200 warm-up
        if not g[i - 1]:
            used = False                      # new green period resets the "first touch"
        if pos is not None:
            ex = None
            if exit_rule == "bands_red" and not g[i]:
                ex = (cl[i], "bands red")
            elif exit_rule == "close<ema100" and cl[i] < e100[i]:
                ex = (cl[i], "close < EMA100")
            elif exit_rule == "close<ema200" and cl[i] < e200[i]:
                ex = (cl[i], "close < EMA200")
            elif exit_rule == "stack_broken" and not (e50[i] > e100[i] > e200[i]):
                ex = (cl[i], "stack broken")
            elif exit_rule.startswith("2R"):  # stop below EMA100 at entry, target 2R
                if l[i] <= pos["stop"]:
                    ex = (min(o[i], pos["stop"]), "stop")
                elif h[i] >= pos["tp"]:
                    ex = (max(o[i], pos["tp"]), "target 2R")
            if ex:
                px, why = ex
                ret = (px / pos["entry"]) * (1 - COST) / (1 + COST) - 1
                trades.append({**pos, "exit_time": idx[i], "exit": px, "reason": why, "ret_%": 100 * ret})
                pos = None
                continue
        if pos is None and not used and g[i - 1] and e50[i - 1] > e100[i - 1] > e200[i - 1] \
                and cl[i - 1] > e50[i - 1] and l[i] <= e50[i - 1]:
            entry = min(o[i], e50[i - 1])
            used = True
            pos = {"entry_time": idx[i], "entry": entry}
            if exit_rule.startswith("2R"):
                stop = e100[i - 1]
                if stop >= entry:
                    pos = None; continue
                pos["stop"], pos["tp"] = stop, entry + 2 * (entry - stop)
            # same-day stop check for 2R
            if exit_rule.startswith("2R") and l[i] <= pos["stop"]:
                ret = (pos["stop"] / entry) * (1 - COST) / (1 + COST) - 1
                trades.append({**pos, "exit_time": idx[i], "exit": pos["stop"], "reason": "stop", "ret_%": 100 * ret})
                pos = None
    if pos is not None:
        ret = (cl[-1] / pos["entry"]) * (1 - COST) / (1 + COST) - 1
        trades.append({**pos, "exit_time": idx[-1], "exit": cl[-1], "reason": "still open", "ret_%": 100 * ret})
    return pd.DataFrame(trades)


def summarize(t, d, label):
    if t.empty:
        return {"label": label, "trades": 0}
    eq = (1 + t["ret_%"] / 100).cumprod()
    days_in = sum((b - a).days for a, b in zip(t.entry_time, t.exit_time))
    span = (d.index[-1] - d.index[201]).days
    total = eq.iloc[-1] - 1
    # max drawdown on daily mark-to-market
    dd = mtm_dd(t, d)
    bh = d["close"].iloc[-1] / d["close"].iloc[201] - 1
    return {"label": label, "trades": len(t), "win_%": round(100 * (t["ret_%"] > 0).mean(), 1),
            "avg_trade_%": round(t["ret_%"].mean(), 1), "best_%": round(t["ret_%"].max(), 1),
            "worst_%": round(t["ret_%"].min(), 1), "total_%": round(100 * total, 1),
            "CAGR_%": round(100 * ((1 + total) ** (365 / span) - 1), 1), "maxDD_%": round(dd, 1),
            "time_in_market_%": round(100 * days_in / span, 1),
            "buy&hold_%": round(100 * bh, 1)}


def mtm_dd(t, d):
    c = d["close"]; eq = pd.Series(1.0, index=d.index[201:]); val = 1.0
    for _, r in t.iterrows():
        seg = c.loc[r.entry_time:r.exit_time]
        path = val * seg / r.entry
        path.iloc[-1] = val * (1 + r["ret_%"] / 100)
        eq.loc[r.entry_time:r.exit_time] = path.values
        val = path.iloc[-1]
        eq.loc[r.exit_time:] = val
    return 100 * (eq / eq.cummax() - 1).min()


if __name__ == "__main__":
    out = os.path.join(ct.HERE, "results")
    pd.set_option("display.width", 220)
    btc = load_ohlc("BTC")
    rows = []
    for rule in ("bands_red", "close<ema100", "close<ema200", "stack_broken", "2R"):
        t = run(btc, rule)
        rows.append(summarize(t, btc, f"BTC, exit: {rule}"))
        if rule == "bands_red":
            t.to_csv(os.path.join(out, "ema50_touch_btc_trades.csv"), index=False)
            print(t.to_string(index=False))
            main_trades = t
    print("\n" + pd.DataFrame(rows).to_string(index=False))
    pd.DataFrame(rows).to_csv(os.path.join(out, "ema50_touch_btc_exits.csv"), index=False)

    # same rule on every coin
    rows = []
    for coin in ct.COINS:
        d = load_ohlc(coin)
        if len(d) < 400: continue
        rows.append(summarize(run(d), d, coin))
    pc = pd.DataFrame(rows)
    print("\nMain rule (exit bands red) on every coin:\n" + pc.to_string(index=False))
    pc.to_csv(os.path.join(out, "ema50_touch_per_coin.csv"), index=False)

    # chart: BTC price with EMAs and trades
    SURF, INK, INK2, BLUE, GRAY, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#8a8984", "#e6e5e1"
    c = btc["close"]; e = {n: c.ewm(span=n, adjust=False).mean() for n in (50, 100, 200)}
    fig, a = plt.subplots(figsize=(11, 5.5), facecolor=SURF); a.set_facecolor(SURF)
    for s in ("top", "right"): a.spines[s].set_visible(False)
    for s in ("left", "bottom"): a.spines[s].set_color(GRID)
    a.tick_params(colors=INK2, labelsize=9); a.grid(axis="y", color=GRID, lw=0.8)
    sl = slice(btc.index[201], None)
    a.plot(c.loc[sl], color=GRAY, lw=1, label="BTC close")
    for n, col in ((50, "#2a78d6"), (100, "#eb6834"), (200, "#6250d6")):
        a.plot(e[n].loc[sl], color=col, lw=1.5, label=f"EMA {n}")
    for _, r in main_trades.iterrows():
        a.plot([r.entry_time, r.exit_time], [r.entry, r.exit], color="#008300" if r["ret_%"] > 0 else "#e34948", lw=2.5)
        a.scatter([r.entry_time], [r.entry], color=INK, s=18, zorder=5)
    a.set_yscale("log"); a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    a.legend(frameon=False, fontsize=9, loc="upper left")
    a.set_title("BTC daily — EMA50 first-touch longs (dot = entry, line to exit; green = win, red = loss)", loc="left", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(os.path.join(out, "ema50_touch_btc.png"), dpi=150, facecolor=SURF)
