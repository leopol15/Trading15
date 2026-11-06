# Trading15 — BTC backtest: 4H liquidity → 15m BOS retest → daily VP targets

**Data:** Binance BTCUSDT spot, 15m candles, 1 Jan 2023 – 31 Oct 2026 (134,395 candles).
**Sizing:** $10,000 start, 1% of equity risked per trade, 0.04% fee per side.

## Result (rules as given)

| Trades | Win rate | Avg R | Total R | Profit factor | Return | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 219 | 35.6% | −0.19 | −40.5 R | 0.66 | −34.0% | −35.0% |

![equity](results/equity.png)

| Exit reason | Trades | Avg R | Sum R |
|---|---:|---:|---:|
| Stop loss | 87 | −1.12 | −97.4 |
| Closed at 22:00 (session end) | 114 | +0.21 | +23.5 |
| TP at VAH (longs) | 9 | +1.65 | +14.9 |
| TP at VAL (shorts) | 8 | +2.16 | +17.3 |
| TP at 4H liquidity | 1 | +1.30 | +1.3 |

| Year | Trades | Win rate | Net R |
|---|---:|---:|---:|
| 2023 | 39 | 43.6% | −4.8 |
| 2024 | 60 | 38.3% | −1.5 |
| 2025 | 70 | 30.0% | −14.2 |
| 2026 | 50 | 34.0% | −19.9 |

Longs: 99 trades, −15.5 R · Shorts: 120 trades, −24.9 R.

**Verdict:** as implemented, the strategy loses on BTC. Every year is negative, both
directions are negative, and 12 of 13 parameter variants (below) are negative too.
The one break-even variant (BOS within 2h of the sweep: +1.7 R over 80 trades) is
within noise, not an edge.

Key observations:
* Only 18 of 219 trades (8%) reach the VAH/VAL/4H-liquidity target before 22:00.
  The previous day's value area is usually too far away for an intraday hold.
* More than half of trades are closed at 22:00 for a small average gain (+0.21 R),
  which cannot pay for the 87 full stop-outs.
* Fees alone cost ~0.1 R per trade (stops are tight, ~1% of price).

## Sensitivity (`results/variants.csv`)

| Variant | Trades | Win % | Avg R | Total R | PF | Return | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Base (rules as given)** | 219 | 35.6 | −0.19 | −40.5 | 0.66 | −34.0% | −35.0% |
| No fees | 219 | 39.3 | −0.09 | −18.6 | 0.81 | −17.9% | −22.1% |
| Hold past 22:00 | 203 | 30.5 | −0.12 | −24.0 | 0.84 | −23.3% | −28.3% |
| No min R:R filter | 298 | 40.3 | −0.15 | −43.3 | 0.69 | −36.0% | −37.2% |
| Min R:R 2 | 139 | 31.7 | −0.21 | −28.6 | 0.65 | −25.5% | −28.2% |
| 4H pivot strength 3 | 163 | 33.1 | −0.21 | −34.2 | 0.59 | −29.6% | −31.2% |
| 4H pivot strength 5 | 96 | 31.2 | −0.31 | −29.9 | 0.42 | −26.1% | −26.9% |
| 15m pivot strength 1 | 346 | 36.1 | −0.13 | −44.7 | 0.76 | −37.6% | −39.1% |
| 15m pivot strength 3 | 150 | 42.0 | −0.07 | −10.3 | 0.84 | −10.5% | −12.5% |
| Retest window 1h | 197 | 36.0 | −0.15 | −29.9 | 0.71 | −26.6% | −29.4% |
| Retest window 4h | 224 | 35.7 | −0.20 | −43.7 | 0.64 | −36.1% | −37.1% |
| BOS within 2h of sweep | 80 | 48.8 | +0.02 | +1.7 | 1.03 | +1.2% | −13.0% |
| BOS within 8h of sweep | 323 | 35.3 | −0.21 | −69.0 | 0.62 | −50.7% | −52.0% |

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
7. **Session** — entries only 10:00–22:00 Europe/Sofia (Plovdiv; daylight-saving handled).
   Unfilled orders are cancelled and open trades closed at 22:00.
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
