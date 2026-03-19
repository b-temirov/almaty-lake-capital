import json
import logging
from typing import Callable, Dict, Optional

import pandas as pd
import websocket

from bot.data.historical.binance_rest import SUPPORTED_INTERVALS


logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    def __init__(
        self,
        base_url: str = "wss://stream.binance.us:9443/ws",
        time_zone: str = "+08:00",
    ):
        self.base_url = base_url.rstrip("/")
        self.time_zone = time_zone

    def _build_stream_name(self, symbol: str, interval: str):
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")

        return f"{symbol.lower()}@kline_{interval}"

    def _build_stream_url(self, symbol: str, interval: str):
        stream_name = self._build_stream_name(symbol, interval)
        return f"{self.base_url}/{stream_name}"

    def _normalize_kline_message(self, payload: Dict) -> Dict:
        kline = payload["k"]
        return {
            "event_type": payload["e"],
            "event_time": pd.to_datetime(payload["E"], unit="ms", utc=True),
            "symbol": payload["s"],
            "open_time": pd.to_datetime(kline["t"], unit="ms", utc=True),
            "close_time": pd.to_datetime(kline["T"], unit="ms", utc=True),
            "interval": kline["i"],
            "open": float(kline["o"]),
            "high": float(kline["h"]),
            "low": float(kline["l"]),
            "close": float(kline["c"]),
            "volume": float(kline["v"]),
            "number_of_trades": int(kline["n"]),
            "quote_asset_volume": float(kline["q"]),
            "taker_buy_base_volume": float(kline["V"]),
            "taker_buy_quote_volume": float(kline["Q"]),
            "is_closed": bool(kline["x"]),
        }

    def stream_klines_df(
        self,
        symbol: str,
        interval: str = "1m",
        on_message: Optional[Callable[[pd.DataFrame], None]] = None,
        closed_only: bool = True,
        time_zone: Optional[str] = None,
    ):
        stream_url = self._build_stream_url(symbol, interval)
        logger.info(
            "Opening Binance websocket stream symbol=%s interval=%s time_zone=%s url=%s",
            symbol.upper(),
            interval,
            self.time_zone if time_zone is None else time_zone,
            stream_url,
        )

        ws = websocket.create_connection(stream_url)

        try:
            while True:
                raw_message = ws.recv()
                payload = json.loads(raw_message)
                candle = self._normalize_kline_message(payload)

                if closed_only and not candle["is_closed"]:
                    continue

                df = pd.DataFrame([candle])
                logger.debug(
                    "Received websocket kline symbol=%s interval=%s open_time=%s is_closed=%s",
                    candle["symbol"],
                    candle["interval"],
                    candle["open_time"],
                    candle["is_closed"],
                )

                if on_message is not None:
                    on_message(df)
                else:
                    yield df
        finally:
            logger.info(
                "Closing Binance websocket stream symbol=%s interval=%s",
                symbol.upper(),
                interval,
            )
            ws.close()
