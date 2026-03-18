from bot.backtesting.backtester import CryptoStrategy

import numpy as np
import pandas as pd


class SMAStrategy(CryptoStrategy):
    """Simple moving average crossover strategy."""

    def __init__(self, fast_window: int = 10, slow_window: int = 50):
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("Moving-average windows must be positive")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")

        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        data["sma_fast"] = data["close"].rolling(window=self.fast_window).mean()
        data["sma_slow"] = data["close"].rolling(window=self.slow_window).mean()
        data["signal"] = np.where(data["sma_fast"] > data["sma_slow"], 1, 0)
        return data
