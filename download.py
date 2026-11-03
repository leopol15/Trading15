"""Download 5m USDT-M perpetual klines (Binance public S3 mirror; prices track Bybit perps closely)."""
import io, sys, zipfile, urllib.request, concurrent.futures as cf, pandas as pd, os
B = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/futures/um/monthly/klines"
# Top-cap coins that have USDT perpetuals on Bybit (stablecoins / wrapped tokens excluded)
COINS = ["BTC","ETH","XRP","BNB","SOL","DOGE","ADA","TRX","LINK","AVAX","SUI","XLM","TON","HBAR",
         "BCH","LTC","DOT","UNI","NEAR","APT","AAVE","ETC","HYPE","ICP","FIL","ARB","OP","ATOM"]
MONTHS = [f"{y}-{m:02d}" for y in (2023,2024,2025,2026) for m in range(1,13) if f"{y}-{m:02d}" <= "2026-10"]
TF = sys.argv[1] if len(sys.argv) > 1 else "5m"
def get(sym, mo):
    try:
        raw = urllib.request.urlopen(f"{B}/{sym}/{TF}/{sym}-{TF}-{mo}.zip", timeout=60).read()
    except Exception:
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), header=None)
    if not str(df.iloc[0, 0]).isdigit(): df = df.iloc[1:]
    df = df.iloc[:, :6]; df.columns = ["t","o","h","l","c","v"]
    return df.astype(float)
for c in COINS:
    sym = c + "USDT"; out = f"data/{sym}_{TF}.parquet"
    if os.path.exists(out): continue
    with cf.ThreadPoolExecutor(8) as ex:
        parts = [p for p in ex.map(lambda m: get(sym, m), MONTHS) if p is not None]
    if not parts: print("missing", sym); continue
    df = pd.concat(parts).drop_duplicates("t").sort_values("t")
    df["t"] = pd.to_datetime(df.t.astype("int64"), unit="ms", utc=True)
    df.set_index("t").to_parquet(out); print(sym, len(df), df.t.iloc[0], flush=True)
