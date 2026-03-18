#!/bin/bash

STORE_DIRECTORY=bot/data \
python3 fetcher/python/download-kline.py \
  -t spot \
  -s BTCUSDT \
  -startDate 2026-03-17 \
  -endDate 2026-03-17 \
  -skip-monthly 1
