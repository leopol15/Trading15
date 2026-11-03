import itertools, sys, pandas as pd, numpy as np
from multiprocessing import Pool
import bt, strategies as S
IS = ("2023-01-01", "2025-01-01")
GRIDS = {
 "breakout": dict(tf=["1h","15min"], n=[24,48], vol_x=[1.0,2.0], atr_sl=[1.5,3.0], tp_r=[3,20], trail_r=[0.0,2.0], btc_filter=[False,True]),
 "trend_pullback": dict(tf=["1h","15min"], rsi_lo=[35,40], look=[12], atr_sl=[1.5,3.0], tp_r=[3,20], trail_r=[0.0,2.0], btc_filter=[False,True]),
}
def net_R(t):
    hold = (t.t_out - t.t_in).dt.total_seconds()/3600
    g = t.side*(t.exit-t.entry)/t.entry
    return (g - 2*(bt.FEE+bt.SLIP) - bt.FUND_8H*hold/8)/t.stop_pct
def job(args):
    name, p, intraday = args
    fn = getattr(S, name); out = []
    for c in bt.COINS:
        out.append(bt.run_coin(c, fn, p, *IS, intraday=intraday))
    t = pd.concat([o for o in out if len(o)]); R = net_R(t)
    yr = t.t_in.dt.year
    return dict(strat=name, intraday=intraday, params=str(p), ntr=len(t), avgR=R.mean(), grossR=(t.side*(t.exit-t.entry)/t.entry/t.stop_pct).mean(), win=(R>0).mean(),
                R2023=R[yr==2023].mean(), R2024=R[yr==2024].mean(),
                coins_pos=(R.groupby(t.coin.values).mean()>0).sum(), stop=t.stop_pct.median())
if __name__ == "__main__":
    jobs = []
    for name, g in GRIDS.items():
        for vals in itertools.product(*g.values()):
            for intra in (False,):
                jobs.append((name, dict(zip(g, vals)), intra))
    with Pool(4) as pool: res = pool.map(job, jobs, chunksize=2)
    df = pd.DataFrame(res).sort_values("avgR", ascending=False)
    df.to_csv("research_is.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(df.head(25).round(3).to_string())
    print(df.groupby(["strat","intraday"]).avgR.describe().round(3))
