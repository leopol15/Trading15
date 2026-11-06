# Trading15 — BTC backtest: 4H liquidity → 15m BOS retest → daily VP targets + Michael's EMA bands

**Data:** Binance BTCUSDT spot, 15m candles, 1 Jan 2023 – 31 Oct 2026 (134,395 candles).
**Sizing:** $10,000 start, 1% of equity risked per trade, 0.04% fee per side.

## Result (rules as given, with Michael's EMA bands on 4H)

**Michael's EMA bands** = EMA 12 / EMA 21 (TradingView "Michael's EMA"). Green (EMA12 > EMA21)
→ only longs; red (EMA12 < EMA21) → only shorts. Default timeframe here is **4H**, using only
closed 4H candles. Trades are **opened** 10:00–22:00 Plovdiv time and then run to TP/SL.

| Trades | Win rate | Avg R | Total R | Profit factor | Return | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 64 | 34.4% | −0.14 | −8.8 R | 0.81 | −9.0% | −14.6% |

Without the bands it was 203 trades, −24.0 R, −23.3%, max DD −28.3%. The 4H bands remove about
two thirds of the trades and cut the loss, but the strategy is still negative.

![equity](results/equity.png)

| Exit reason | Trades | Avg R | Sum R |
|---|---:|---:|---:|
| Stop loss | 42 | −1.13 | −47.5 |
| TP at VAH (longs) | 15 | +1.90 | +28.5 |
| TP at VAL (shorts) | 5 | +1.47 | +7.4 |
| TP at 4H liquidity | 2 | +1.41 | +2.8 |

| Year | Trades | Win rate | Net R |
|---|---:|---:|---:|
| 2023 | 15 | 33.3% | −1.2 |
| 2024 | 17 | 23.5% | −6.1 |
| 2025 | 20 | 50.0% | +3.9 |
| 2026 | 12 | 25.0% | −5.4 |

| Side | Trades | Net R |
|---|---:|---:|
| Longs (green band) | 33 | **+8.2** |
| Shorts (red band) | 31 | **−17.0** |

**Band timeframe matters a lot.** This is a reversal setup (sweep a low → go long), while the
bands follow the trend. Sweeping a low usually turns a fast band red, so the long gets blocked:
* **15m bands:** 49 trades, +5.7 R, PF 1.15, +5.2%, max DD −6.3%. This is the only band
  timeframe that is positive with both directions.
* **1H bands:** only 3 trades in almost 4 years; the band almost never flips back in time.
* **4H bands:** 64 trades, −8.8 R (the result above).
* **1D bands:** 104 trades, −21.5 R.

As before, the shorts are the problem. **4H bands, longs only:** 33 trades, 45.5% win rate,
+8.2 R, PF 1.36, +8.1%, max DD −5.8%. Without the bands, longs only gave +24.3 R on 97 trades,
so for longs the band filter removes more winners than losers.

Caveats: sample sizes are small (3–104 trades), BTC rose from ~$16.5k to ~$78k over the period,
and the best timeframes were chosen after seeing the results.

## Sensitivity (`results/variants.csv`)

| Variant | Trades | Win % | Avg R | Total R | PF | Return | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Base: Michael bands 4H (EMA 12/21)** | 64 | 34.4 | −0.14 | −8.8 | 0.81 | −9.0% | −14.6% |
| No Michael bands (previous base) | 203 | 30.5 | −0.12 | −24.0 | 0.84 | −23.3% | −28.3% |
| Michael bands 15m | 49 | 38.8 | +0.12 | +5.7 | 1.15 | +5.2% | −6.3% |
| Michael bands 1H | 3 | 66.7 | +0.41 | +1.2 | 2.08 | +1.2% | −1.1% |
| Michael bands 1D | 104 | 29.8 | −0.21 | −21.5 | 0.74 | −20.2% | −26.8% |
| Michael bands 4H, slope mode | 12 | 33.3 | −0.26 | −3.1 | 0.65 | −3.2% | −4.4% |
| Michael bands 1H, slope mode | 20 | 35.0 | −0.09 | −1.7 | 0.86 | −1.9% | −9.2% |
| 4H bands + BOS within 2h | 22 | 45.5 | +0.23 | +5.0 | 1.33 | +4.8% | −4.7% |
| 4H bands, longs only | 33 | 45.5 | +0.25 | +8.2 | 1.36 | +8.1% | −5.8% |
| 4H bands, shorts only | 31 | 22.6 | −0.55 | −17.0 | 0.36 | −15.8% | −15.8% |
| 4H bands, no fees | 64 | 34.4 | −0.02 | −1.1 | 0.96 | −1.7% | −11.1% |
| 4H bands, force-close at 22:00 | 64 | 31.2 | −0.26 | −16.9 | 0.55 | −15.9% | −18.9% |
| 4H bands, 15m pivot strength 3 | 37 | 35.1 | −0.09 | −3.2 | 0.87 | −3.5% | −6.2% |
| 4H bands, min R:R 2 | 34 | 17.6 | −0.46 | −15.8 | 0.51 | −15.0% | −20.1% |

## How the rules were coded

Your description leaves some choices open; these are the ones made (all are
parameters in `Params` in `backtest.py`):

1. **4H liquidity** — 4H swing highs (buy-side) and swing lows (sell-side): a 4H candle
   whose high/low is the extreme of the 2 candles on each side. A level is only used
   once that swing is confirmed (no look-ahead) and is deleted once price trades through it.
2. **Sweep** — a 15m candle trades through an active 4H level. Swept low → look for a long;
   swept high → look for a short.
3. **15m BOS** — within 4h (16 candles) of the sweep, a 15m candle **closes** beyond the latest
   confirmed 15m swing high (long) / swing low (short) (2-bar pivots).
4. **Entry on the retest** — limit order at the broken BOS level, valid for 2h (8 candles).
   Cancelled if price reaches the target first. Stop = sweep extreme ± 0.05%.
5. **Daily fixed volume profile** — built from the previous UTC day's 15m candles
   (200 price bins, volume spread evenly over each candle's range), 70% value area.
6. **Exit** — long: TP at VAH or the nearest 4H buy-side liquidity above entry, whichever is
   closer (hit first). Short: TP at VAL or nearest 4H sell-side liquidity. Trades whose target
   offers less than 1:1 are skipped.
7. **Session** — trades are opened only 10:00–22:00 Europe/Sofia (Plovdiv; daylight-saving
   handled). Unfilled orders are cancelled at 22:00; open trades keep running to TP/SL.
8. **Michael's EMA bands** — EMA 12 / EMA 21 on closed 4H candles (`band_tf`). A long BOS is only
   taken while the band is green (EMA12 > EMA21), a short BOS only while it is red. If the BOS
   candle has the wrong colour, the setup keeps waiting for a later BOS inside the window.
   `band_mode="slope"` is the alternative colouring (green only when both EMAs rise).
9. **Conservative fills** — if stop and target are both inside one candle, the stop counts;
   on the fill candle only the stop is checked. One position at a time.

## Reproduce

```bash
pip install pandas numpy matplotlib
./download_data.sh          # Binance monthly 15m files -> data/raw/
python3 backtest.py         # base run -> results/trades.csv
python3 variants.py         # sensitivity -> results/variants.csv
python3 make_chart.py       # -> results/equity.png
```

Every trade (sweep time, BOS time, entry, stop, target, exit, R) is in `results/trades.csv`.
