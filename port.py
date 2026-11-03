import pandas as pd, bt
t = pd.read_parquet("trades_final_raw.parquet")
rows = []
for start in ["2021-01-01", "2023-01-01", "2025-01-01"]:
    tt = t[t.t_in >= pd.Timestamp(start, tz="UTC")]
    for risk in [0.005, 0.01, 0.015, 0.02, 0.03]:
        for mp in [3, 5, 8]:
            res, cur = bt.portfolio(tt, 1000, risk, mp)
            rows.append(dict(start=start, risk=risk, max_pos=mp, **bt.stats(res, cur)))
pd.set_option("display.width", 200)
print(pd.DataFrame(rows).to_string())
