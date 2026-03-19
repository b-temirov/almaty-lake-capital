from bot.backtesting.backtester import CryptoStrategy
from bot.strategy.discovery.bounce_percentages import calculate_market_events
from bot.strategy.discovery.bounce_slope_filters import (
    get_nonnegative_slope_timestamps,
)

import pandas as pd


class BounceSlopeStrategy(CryptoStrategy):
    """Long-only event strategy based on slope-filtered upper-band bounces."""

    def __init__(
        self,
        rolling_window: int,
        atr: float,
        slope_window: int = 75,
        hold_periods: int = 1,
    ):
        if rolling_window <= 0:
            raise ValueError("rolling_window must be positive")
        if atr <= 0:
            raise ValueError("atr must be positive")
        if slope_window <= 0:
            raise ValueError("slope_window must be positive")
        if hold_periods <= 0:
            raise ValueError("hold_periods must be positive")

        self.rolling_window = rolling_window
        self.atr = atr
        self.slope_window = slope_window
        self.hold_periods = hold_periods

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        data["ma"] = data["close"].rolling(window=self.rolling_window).mean()
        data["l_bound"] = data["ma"] - self.atr * 0.5
        data["u_bound"] = data["ma"] + self.atr * 0.5

        bounce_indices, pen_indices = calculate_market_events(
            data["close"],
            data["l_bound"],
            data["u_bound"],
            self.rolling_window,
        )

        nonnegative_slope_timestamps = get_nonnegative_slope_timestamps(
            data["open_time"],
            data["u_bound"],
            window=self.slope_window,
        )

        filtered_bounce_indices = data.loc[bounce_indices, "open_time"]
        filtered_bounce_indices = filtered_bounce_indices[
            filtered_bounce_indices.isin(nonnegative_slope_timestamps)
        ].index.tolist()

        data["bounce_event"] = 0
        data.loc[filtered_bounce_indices, "bounce_event"] = 1

        if self.hold_periods == 1:
            data["signal"] = data["bounce_event"]
        else:
            data["signal"] = (
                data["bounce_event"]
                .rolling(window=self.hold_periods, min_periods=1)
                .max()
                .astype(int)
            )

        data["signal"] = data["signal"].fillna(0).astype(int)
        data["pen_event"] = 0
        data.loc[pen_indices, "pen_event"] = 1
        data["slope_nonnegative"] = data["open_time"].isin(nonnegative_slope_timestamps)

        return data
