from enum import Enum, auto
from collections import deque
import pandas as pd
import numpy as np
from bot.backtesting.backtester import CryptoStrategy

class PositionState(Enum):
    NEUTRAL = auto()
    ABOVE = auto()
    UNDER = auto()
    INSIDE = auto()
    WAIT = auto()

class IndicatorCalculator:
    """Handles sliding window calculations efficiently."""
    def __init__(self, ma_window: int, slope_window: int):
        self.ma_window = ma_window
        self.slope_window = slope_window
        self.prices = deque(maxlen=max(ma_window, slope_window))
        self.weights = np.arange(slope_window, dtype=np.float64) - (slope_window - 1) / 2

    def update(self, price: float):
        self.prices.append(price)

    @property
    def ma(self):
        if len(self.prices) < self.ma_window:
            return None
        return np.mean(list(self.prices)[-self.ma_window:])

    @property
    def is_slope_positive(self):
        if len(self.prices) < self.slope_window:
            return False
        recent_prices = np.array(list(self.prices)[-self.slope_window:])
        return np.dot(recent_prices, self.weights) >= 0

class BounceSlopeStrategy(CryptoStrategy):
    def __init__(self, rolling_window: int, atr: float, slope_window: int = 2, hold_periods: int = 1):
        super().__init__()
        self.params = {
            'rolling_window': rolling_window,
            'atr': atr,
            'slope_window': slope_window,
            'hold_periods': hold_periods
        }
        self.calc = IndicatorCalculator(rolling_window, slope_window)
        self.state = PositionState.NEUTRAL
        self.prev_state = PositionState.NEUTRAL # Track where we entered INSIDE from

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Vectorized-friendly wrapper or optimized loop."""
        # Logic for batch processing. 
        # Note: For backtesting, vectorized pandas/numpy is 100x faster than itertuples.
        results = []
        for row in df.itertuples():
            results.append(self.runner(row))
        
        df['signal'] = results
        return df

    def runner(self, row):
        self.calc.update(row.close)
        ma = self.calc.ma
        
        if ma is None or not self.calc.is_slope_positive:
            return 0
            
        return self._process_state_machine(row.close, ma)

    def _process_state_machine(self, price, ma):
        ubound = ma + self.params['atr'] / 2
        lbound = ma - self.params['atr'] / 2
        signal = 0

        # simplified logic flow using state tracking
        if price > ubound:
            if self.state == PositionState.INSIDE and self.prev_state == PositionState.ABOVE:
                signal = -1
            self.state = PositionState.ABOVE
        elif price < lbound:
            self.state = PositionState.UNDER
        else:
            # Price is INSIDE bounds
            if self.state != PositionState.INSIDE:
                self.prev_state = self.state
                if self.state == PositionState.ABOVE:
                    signal = 1
                self.state = PositionState.INSIDE
        
        return signal