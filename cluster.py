import pandas as pd, numpy as np
from variants import summ
rows=[]
for v in ["base","sl2"]:
    t = pd.read_parquet(f"var_{v}.parquet").sort_values("t_in")
    for k in [1, 2, 3, 99]:
        tt = t.groupby("t_in").head(k)           # max k new entries per hour (first by coin order = market-cap order)
        for mp in [6, 10, 99]:
            open_=[]; out=[]
            for r in tt.itertuples():
                open_=[o for o in open_ if o>r.t_in]
                if len(open_)>=mp: continue
                open_.append(r.t_out); out.append((r.t_out,r.R))
            s=pd.Series([x[1] for x in out],index=[x[0] for x in out]).sort_index()
            rows.append(dict(var=v,per_hour=k,max_pos=mp,avgR=round(s.mean(),3),**summ(s)))
pd.set_option("display.width",250); print(pd.DataFrame(rows).to_string())
