import pandas as pd, numpy as np, bt, strategies as S, sys
from multiprocessing import Pool
from research import net_R
BASE = dict(tf="1h", n=48, vol_x=2.0, atr_sl=1.5, tp_r=20, trail_r=0.0, btc_filter=False)
VARS = {"base": {}, "btcf": {"btc_filter": True}, "trail3": {"trail_r": 3.0}, "trail2": {"trail_r": 2.0},
        "be1.5": {"be_r": 1.5}, "tp8": {"tp_r": 8}, "sl2": {"atr_sl": 2.0}, "vol3": {"vol_x": 3.0}, "n72": {"n": 72}}
def one(a):
    v, c = a
    return bt.run_coin(c, S.breakout, {**BASE, **VARS[v]}, "2021-01-01", "2026-11-01", day_hours=(14, 22))
def portR(t, max_pos, same_dir_max=99):
    t = t.sort_values("t_in"); open_ = []; out = []
    for r in t.itertuples():
        open_ = [o for o in open_ if o[0] > r.t_in]
        if len(open_) >= max_pos or any(o[1] == r.coin for o in open_): continue
        if sum(o[2] == r.side for o in open_) >= same_dir_max: continue
        open_.append((r.t_out, r.coin, r.side)); out.append((r.t_out, r.R))
    s = pd.Series([x[1] for x in out], index=[x[0] for x in out]).sort_index()
    return s
def summ(s):
    cum = s.cumsum(); dd = (cum - cum.cummax()).min()
    y = s.groupby(s.index.year).sum().round(0)
    return dict(n=len(s), totR=round(s.sum()), ddR=round(dd), ratio=round(s.sum()/-dd, 2), **{str(k): v for k, v in y.items()})
if __name__ == "__main__":
    rows = []
    with Pool(4) as pool:
        for v in VARS:
            t = pd.concat([x for x in pool.map(one, [(v, c) for c in bt.COINS]) if len(x)])
            t["R"] = net_R(t).values; t.to_parquet(f"var_{v}.parquet")
            for mp, sd in [(5, 99), (5, 3), (8, 3), (99, 99)]:
                rows.append(dict(var=v, max_pos=mp, same_dir=sd, **summ(portR(t, mp, sd))))
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string())
