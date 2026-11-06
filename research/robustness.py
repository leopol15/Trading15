"""Robustness: every single-coin rule on every coin, plus 1-day execution delay and 2x costs."""
import os, numpy as np, pandas as pd
import crypto_trend as ct

C, H, L = ct.load()
rules = {**{f"SMA-{n}": (lambda n: lambda: ct.sig_sma(C, H, L, n))(n) for n in (20, 50, 100, 150, 200)},
         **{f"DONCH-{n}": (lambda n: lambda: ct.sig_donchian(C, H, L, n))(n) for n in (20, 55)},
         "TSMOM": lambda: ct.sig_tsmom(C, H, L)}
rows = []
for rname, f in rules.items():
    S = f()
    for coin in C.columns:
        c = C[coin].dropna()
        if len(c) < 600: continue
        start = c.index[0] + pd.Timedelta(days=200)
        r = c.pct_change().loc[start:]
        for delay, cost, tag in ((1, ct.COST, "base"), (2, ct.COST, "delay+1d"), (1, 2 * ct.COST, "2x cost")):
            s = S[coin].reindex(c.index).fillna(0)
            pos = s.shift(delay).loc[start:]
            ret = pos * r - s.diff().abs().shift(delay - 1).loc[start:].fillna(0) * cost
            for per, (a, b) in {"IS": (start, ct.IS_END), "OOS": ("2023-01-01", c.index[-1])}.items():
                sr, br = ret.loc[a:b], r.loc[a:b]
                m, bm = ct.metrics(sr), ct.metrics(br)
                if not m: continue
                rows.append(dict(rule=rname, coin=coin, test=tag, period=per,
                                 cagr=m["CAGR_%"], bh_cagr=bm["CAGR_%"], sharpe=m["Sharpe"], bh_sharpe=bm["Sharpe"],
                                 dd=m["maxDD_%"], bh_dd=bm["maxDD_%"]))
d = pd.DataFrame(rows)
d.to_csv(os.path.join(ct.HERE, "results", "robustness_per_coin.csv"), index=False)
d["profitable"] = d.cagr > 0
d["beats_bh_sharpe"] = d.sharpe > d.bh_sharpe
d["smaller_dd"] = d.dd > d.bh_dd
pd.set_option("display.width", 200)
print("Share of coins (%) — base costs")
g = d[d.test == "base"].groupby(["period", "rule"])[["profitable", "beats_bh_sharpe", "smaller_dd"]].mean().mul(100).round(0)
print(g.unstack(0).to_string())
print("\nBTC only:")
print(d[(d.coin == "BTC")].pivot_table(index="rule", columns=["period", "test"], values="sharpe").round(2).to_string())
print("\nBTC B&H Sharpe IS/OOS:", d[(d.coin=='BTC')&(d.test=='base')].groupby('period').bh_sharpe.first().to_dict())
print("\nETH only (base):")
print(d[(d.coin == "ETH") & (d.test == "base")].pivot_table(index="rule", columns="period", values=["cagr","sharpe","dd","bh_cagr","bh_sharpe","bh_dd"]).round(2).to_string())
