#!/bin/bash

STORE_DIRECTORY=bot/data \
python3 scripts/python/download-trade.py \
  -t spot \
  -s BTCUSDT \
  -startDate 2026-03-12 \
  -endDate 2026-03-13 \
  -skip-monthly 1
