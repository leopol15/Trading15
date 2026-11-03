import pandas as pd, bt
rows = []
for v in ["base", "sl2"]:
    t = pd.read_parquet(f"var_{v}.parquet").drop(columns=["R"])
    for start in ["2021-01-01", "2025-01-01"]:
        tt = t[t.t_in >= pd.Timestamp(start, tz="UTC")]
        for risk in [0.0025, 0.005, 0.0075]:
            for mp in [10, 20, 40]:
                res, cur = bt.portfolio(tt, 1000, risk, mp)
                s = bt.stats(res, cur); s.pop("avgR")
                rows.append(dict(var=v, start=start[:4], risk=risk, max_pos=mp, **s))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string())
