import pandas as pd, bt, strategies as S
from multiprocessing import Pool
from research import net_R
BASE = dict(tf="1h", n=48, vol_x=2.0, atr_sl=1.5, tp_r=20, trail_r=0.0, btc_filter=False)
VARS = {"base": {}, "hold24": {"_hold": 24}, "hold48": {"_hold": 48}, "n24": {"n": 24}, "vol1.5": {"vol_x": 1.5},
        "vol3": {"vol_x": 3.0}, "sl2": {"atr_sl": 2.0}, "sl1": {"atr_sl": 1.0}, "tp5": {"tp_r": 5}, "intraday": {"_intra": True},
        "btcf": {"btc_filter": True}, "hours9-21": {"_hours": (9, 21)}, "hours0-24": {"_hours": (0, 24)}}
def job(a):
    name, period = a
    p = {**BASE, **VARS[name]}
    hold = p.pop("_hold", 72); intra = p.pop("_intra", False); hrs = p.pop("_hours", (8, 22))
    t = pd.concat([x for x in (bt.run_coin(c, S.breakout, p, *period, intraday=intra, max_hold_h=hold, day_hours=hrs) for c in bt.COINS) if len(x)])
    R = net_R(t); y = t.t_in.dt.year
    return dict(var=name, period=period[0][:4], ntr=len(t), avgR=round(R.mean(), 3), win=round((R>0).mean(), 3),
                **{f"R{k}": round(R[y==k].mean(), 3) for k in (2023, 2024, 2025, 2026)},
                coins_pos=int((R.groupby(t.coin.values).mean() > 0).sum()), ncoins=t.coin.nunique())
if __name__ == "__main__":
    jobs = [(v, per) for v in VARS for per in [("2023-01-01", "2025-01-01"), ("2025-01-01", "2026-11-01")]]
    with Pool(4) as pool: res = pool.map(job, jobs)
    print(pd.DataFrame(res).to_string())
