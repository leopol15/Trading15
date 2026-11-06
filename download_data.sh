#!/usr/bin/env bash
# Download Binance BTCUSDT 15m monthly klines (Jan 2023 - Oct 2026) into data/raw/
set -e
mkdir -p data/raw && cd data/raw
for y in 2023 2024 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  [ "$y$m" \> "202610" ] && continue
  f=BTCUSDT-15m-$y-$m.zip
  curl -sSfO https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/15m/$f && unzip -oq $f && rm $f
done; done
