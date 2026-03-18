import logging
import time
from typing import Any, Dict, List

import pandas as pd
import requests

logger = logging.getLogger(__name__)

SUPPORTED_INTERVALS = {
    "1s",
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
}

INTERVAL_TO_MS = {
    "1s": 1_000,
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "2h": 2 * 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "6h": 6 * 60 * 60_000,
    "8h": 8 * 60 * 60_000,
    "12h": 12 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
    "3d": 3 * 24 * 60 * 60_000,
    "1w": 7 * 24 * 60 * 60_000,
    "1M": 30 * 24 * 60 * 60_000,
}


class BinanceRestClient:
    def __init__(
        self,
        base_url: str = "https://api.binance.us",
        timeout: int = 10,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path, params=None):
        params = dict(params or {})
        start = time.perf_counter()

        try:
            resp = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "GET %s status=%s latency_ms=%.2f params=%s",
                path,
                resp.status_code,
                elapsed_ms,
                params,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "GET %s failed latency_ms=%.2f params=%s",
                path,
                elapsed_ms,
                params,
            )
            raise

    def _validate_kline_request(self, interval, limit, start_time, end_time):
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError("start_time must be <= end_time")

    def _fetch_klines_batch(
        self,
        symbol,
        interval,
        limit,
        start_time=None,
        end_time=None,
        time_zone=None,
    ):
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)
        if time_zone is not None:
            params["timeZone"] = time_zone

        logger.info(
            "klines_df batch called symbol=%s interval=%s limit=%s start_time=%s end_time=%s time_zone=%s",
            symbol.upper(),
            interval,
            limit,
            start_time,
            end_time,
            time_zone,
        )

        rows = self._get("/api/v3/klines", params=params)
        candles = [self._normalize_kline_row(row) for row in rows]

        logger.info(
            "klines_df batch returned symbol=%s interval=%s candles=%s",
            symbol.upper(),
            interval,
            len(candles),
        )
        return candles

    def klines_df(
        self,
        symbol,
        interval="1m",
        limit=1000,
        start_time=None,
        end_time=None,
        time_zone=None,
    ):
        self._validate_kline_request(interval, limit, start_time, end_time)

        if start_time is None or end_time is None:
            candles = self._fetch_klines_batch(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                time_zone=time_zone,
            )
        else:
            candles = []
            current_start_time = int(start_time)
            final_end_time = int(end_time)
            interval_ms = INTERVAL_TO_MS[interval]

            while current_start_time <= final_end_time:
                batch = self._fetch_klines_batch(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    start_time=current_start_time,
                    end_time=final_end_time,
                    time_zone=time_zone,
                )
                if not batch:
                    break

                candles.extend(batch)

                last_open_time = batch[-1]["open_time"]
                next_start_time = last_open_time + interval_ms
                if next_start_time <= current_start_time:
                    break
                current_start_time = next_start_time

        df = pd.DataFrame(candles)

        if not df.empty:
            df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time")
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
            df = df.reset_index(drop=True)

        return df

    def _normalize_kline_row(self, row: List[Any]) -> Dict[str, Any]:
        return {
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "close_time": int(row[6]),
            "quote_asset_volume": float(row[7]),
            "number_of_trades": int(row[8]),
            "taker_buy_base_volume": float(row[9]),
            "taker_buy_quote_volume": float(row[10]),
        }
