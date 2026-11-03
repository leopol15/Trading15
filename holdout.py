import pandas as pd, bt, strategies as S
from multiprocessing import Pool
from research import net_R
P = dict(tf="1h", n=48, vol_x=2.0, atr_sl=1.5, tp_r=20, trail_r=0.0, btc_filter=False)
def one(a):
    c, hrs = a
    return bt.run_coin(c, S.breakout, P, "2021-01-01", "2026-11-01", day_hours=hrs)
if __name__ == "__main__":
    for hrs in [(14, 22), (8, 22), (8, 14)]:
        with Pool(4) as pool: t = pd.concat([x for x in pool.map(one, [(c, hrs) for c in bt.COINS]) if len(x)])
        t["R"] = net_R(t).values; t["yr"] = t.t_in.dt.year
        print("hours", hrs)
        print(t.pivot_table(index="yr", columns="side", values="R", aggfunc=["mean", "count"], margins=True).round(3))
        if hrs == (14, 22): t.to_parquet("trades_final_raw.parquet")
