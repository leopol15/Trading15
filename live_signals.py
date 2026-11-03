"""Live signal scanner for Bybit USDT perpetuals (public market data, no API key needed).
Run it once per hour, a few seconds after the full hour, between 14:00 and 22:00 Plovdiv time:
    python3 live_signals.py --equity 1000 --risk 0.25
It prints entry side, stop-loss, position size (qty) and suggested isolated leverage.
It does NOT place orders. NOTE: could not be tested live from the build environment (Bybit API blocked there)."""
import argparse, json, urllib.request, datetime as dt, pandas as pd
import bt, strategies as S
from final_backtest import PARAMS, HOURS

def klines(sym, limit=1000):
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}&interval=60&limit={limit}"
    rows = json.load(urllib.request.urlopen(url, timeout=20))["result"]["list"]
    df = pd.DataFrame(rows, columns=["t","o","h","l","c","v","turnover"]).astype(float).iloc[::-1]
    df.index = pd.to_datetime(df.t.astype("int64"), unit="ms", utc=True)
    return df[["o","h","l","c","v"]].iloc[:-1]          # drop the still-open candle

def signal_for(d1h):
    d4h = bt.resample(d1h, "4h")
    sig = S.breakout(d1h, d4h, PARAMS)
    return sig.iloc[-1], d1h.c.iloc[-1]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--equity", type=float, default=1000); ap.add_argument("--risk", type=float, default=0.25)
    a = ap.parse_args()
    now = pd.Timestamp.now(tz=bt.TZ)
    if not (HOURS[0] <= now.hour < HOURS[1]): print(f"{now:%H:%M} — извън прозореца {HOURS[0]}:00–{HOURS[1]}:00, без нови входове."); raise SystemExit
    for c in bt.COINS:
        try: last, price = signal_for(klines(c + "USDT"))
        except Exception as e: print(c, "error", e); continue
        if last.side == 0: continue
        sd = last.stop_dist; stop_pct = sd / price
        risk_eur = a.equity * a.risk / 100; notional = risk_eur / stop_pct
        lev = min(50, max(1, int(0.5 / stop_pct)))
        side = "LONG" if last.side > 0 else "SHORT"
        print(f"{c:5s} {side:5s} entry≈{price:.6g}  SL={price - last.side*sd:.6g} ({stop_pct*100:.2f}%)  "
              f"qty={notional/price:.6g}  notional≈{notional:.0f}$  margin≈{notional/lev:.1f}$ @ {lev}x isolated  "
              f"close by {(now + pd.Timedelta(hours=72)):%a %d.%m %H:%M}")
