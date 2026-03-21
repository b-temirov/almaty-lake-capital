from bot.backtesting.backtester import CryptoStrategy

import numpy as np
import pandas as pd


class EMAStrategy(CryptoStrategy):
    """Exponential moving average crossover strategy."""

    def __init__(self, fast_window: int = 12, slow_window: int = 26):
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("Moving-average windows must be positive")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")

        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        data["ema_fast"] = (
            data["close"]
            .ewm(
                span=self.fast_window,
                adjust=False,
            )
            .mean()
        )
        data["ema_slow"] = (
            data["close"]
            .ewm(
                span=self.slow_window,
                adjust=False,
            )
            .mean()
        )
        data["signal"] = np.where(data["ema_fast"] < data["ema_slow"], 1, 0)
        return data
