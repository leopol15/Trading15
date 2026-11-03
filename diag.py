import pandas as pd, numpy as np, bt, strategies as S
from multiprocessing import Pool
from research import net_R
P = dict(tf="1h", n=48, vol_x=2.0, atr_sl=1.5, tp_r=20, trail_r=0.0, btc_filter=False)
def one(c): return bt.run_coin(c, S.breakout, P, "2023-01-01", "2026-11-01")
if __name__ == "__main__":
    with Pool(4) as pool: t = pd.concat([x for x in pool.map(one, bt.COINS) if len(x)])
    t["R"] = net_R(t).values; t["yr"] = t.t_in.dt.year
    t["hr"] = t.t_in.dt.tz_convert(bt.TZ).dt.hour
    t.to_parquet("diag_trades.parquet")
    print(t.pivot_table(index="yr", columns="side", values="R", aggfunc=["mean","count"]).round(3))
    print(t.groupby(pd.cut(t.hr,[7,10,13,16,19,22])).R.agg(["mean","count"]).round(3))
    print(t.groupby("why").R.agg(["mean","count"]).round(3))
