# Trading15 — BTC backtest: 4H liquidity → 15m BOS retest → daily VP targets

**Data:** Binance BTCUSDT spot, 15m candles, 1 Jan 2023 – 31 Oct 2026 (134,395 candles).
**Sizing:** $10,000 start, 1% of equity risked per trade, 0.04% fee per side.

## Result (rules as given)

Trades are **opened** only between 10:00 and 22:00 Plovdiv time; once open they run until
take-profit or stop-loss, overnight if needed (median hold 5.5 h, longest 10 days).

| Trades | Win rate | Avg R | Total R | Profit factor | Return | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 203 | 30.5% | −0.12 | −24.0 R | 0.84 | −23.3% | −28.3% |

![equity](results/equity.png)

| Exit reason | Trades | Avg R | Sum R |
|---|---:|---:|---:|
| Stop loss | 141 | −1.10 | −155.5 |
| TP at VAH (longs) | 34 | +2.34 | +79.7 |
| TP at VAL (shorts) | 23 | +1.92 | +44.2 |
| TP at 4H liquidity | 5 | +1.51 | +7.6 |

| Year | Trades | Win rate | Net R |
|---|---:|---:|---:|
| 2023 | 37 | 27.0% | −7.6 |
| 2024 | 57 | 33.3% | +1.7 |
| 2025 | 65 | 38.5% | +5.8 |
| 2026 | 44 | 18.2% | −23.9 |

| Side | Trades | Net R |
|---|---:|---:|
| Longs | 93 | **+20.1** |
| Shorts | 110 | **−44.1** |

**Verdict:** with both directions the strategy loses (−23%). The damage comes from the
**shorts**; the long side is profitable on its own:

* **Longs only:** 97 trades, 39% win rate, +24.3 R, PF 1.34, +25.4%, max DD −7.4%
  (by year: 2023 +8.8 R, 2024 +1.3 R, 2025 +18.3 R, 2026 −4.1 R).
* **Longs only + BOS within 2h of the sweep:** 41 trades, 49% win rate, +29.8 R, PF 2.26,
  +33.4%, max DD −4.8%.

Caveats: BTC went from ~$16.5k to ~$78k in this period, so a long bias is partly the market's
trend; 41–97 trades is a small sample; and the "longs only / 2h" filters were picked *after*
seeing these results, so they need checking on other data (e.g. 2020–2022, ETH) before being trusted.

## Sensitivity (`results/variants.csv`)

| Variant | Trades | Win % | Avg R | Total R | PF | Return | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Base (rules as given)** | 203 | 30.5 | −0.12 | −24.0 | 0.84 | −23.3% | −28.3% |
| No fees | 203 | 30.5 | −0.02 | −4.2 | 0.96 | −6.5% | −19.2% |
| Force-close at 22:00 | 219 | 35.6 | −0.18 | −40.5 | 0.66 | −34.0% | −35.0% |
| No min R:R filter | 277 | 40.4 | −0.09 | −23.5 | 0.86 | −23.1% | −29.0% |
| Min R:R 2 | 133 | 22.6 | −0.20 | −26.3 | 0.77 | −24.6% | −32.1% |
| 4H pivot strength 3 | 153 | 28.8 | −0.16 | −25.0 | 0.78 | −23.6% | −26.3% |
| 4H pivot strength 5 | 95 | 22.1 | −0.38 | −35.8 | 0.56 | −30.8% | −31.8% |
| 15m pivot strength 1 | 317 | 30.0 | +0.07 | +21.4 | 1.05 | +16.1% | −21.8% |
| 15m pivot strength 3 | 140 | 36.4 | +0.07 | +9.1 | 1.07 | +7.5% | −14.4% |
| Retest window 4 bars (1h) | 184 | 31.5 | −0.07 | −13.5 | 0.89 | −14.7% | −21.7% |
| Retest window 16 bars (4h) | 208 | 29.8 | −0.14 | −29.4 | 0.81 | −27.4% | −29.8% |
| BOS window 8 bars (2h) | 78 | 41.0 | +0.27 | +20.7 | 1.36 | +21.5% | −8.4% |
| BOS window 32 bars (8h) | 297 | 27.3 | −0.23 | −68.9 | 0.71 | −51.5% | −53.2% |
| Longs only | 97 | 39.2 | +0.25 | +24.3 | 1.34 | +25.4% | −7.4% |
| Shorts only | 120 | 24.2 | −0.40 | −47.4 | 0.53 | −38.4% | −38.4% |
| Longs only + BOS within 2h | 41 | 48.8 | +0.73 | +29.8 | 2.26 | +33.4% | −4.8% |

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
8. **Conservative fills** — if stop and target are both inside one candle, the stop counts;
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
