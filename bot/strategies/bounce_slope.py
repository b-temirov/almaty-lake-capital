from bot.backtesting.backtester import CryptoStrategy
from bot.strategy.discovery.bounce_percentages import calculate_market_events
from bot.strategy.discovery.bounce_slope_filters import (
    get_nonnegative_slope_timestamps,
)

from collections import deque 
import pandas as pd
import numpy as np

class Calculator():
    def __init__(self, mover_window_size: int, sloper_window_size: int):
        if mover_window_size <= 0:
            raise ValueError("Mover window size must be a positive integer.")
        
        if sloper_window_size <= 0:
            raise ValueError("Sloper window size must be a positive integer.")
        
        self.mover_window_size = mover_window_size
        self.sloper_window_size = sloper_window_size
        self.mover_queue = deque()
        self.sloper_queue = deque()
        self.current_sum = 0.0
        self.weights = np.arange(sloper_window_size, dtype=np.float64) - (sloper_window_size - 1) / 2
    
    def calculate_ma(self, value):
        if len(self.mover_queue) == self.mover_window_size:
            oldest = self.mover_queue.popleft()
            self.current_sum -= oldest

        self.mover_queue.append(value)
        self.current_sum += value

        if len(self.mover_queue) < self.mover_window_size:
            return None

        return self.current_sum / len(self.mover_queue)
    
    def calculate_slope(self, value):
        if len(self.sloper_queue) == self.sloper_window_size:
            self.sloper_queue.popleft()

        self.sloper_queue.append(value)

        if len(self.sloper_queue) < self.sloper_window_size:
            return False
        
        values_array = np.array(self.sloper_queue, dtype=np.float64)

        if np.isnan(values_array).any():
            return False
        
        slope_numerator = np.dot(values_array, self.weights)

        return slope_numerator >= 0.0


class BounceSlopeStrategy(CryptoStrategy):
    """Long-only event strategy based on slope-filtered upper-band bounces."""

    def __init__(
        self,
        rolling_window: int,
        atr: float,
        slope_window: int = 2,
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
        self.window = []
        self.calculator = Calculator(mover_window_size=self.rolling_window, sloper_window_size=self.slope_window)
        self.above=False
        self.under=False
        self.inside=False
        self.wait=False

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        '''
        This function takes maket data as input and produces signals dataframe using it
        first it loads data
        then iterates thrugh each timestamp in this data to simulate live trading
            each row it passes to function runner
        '''
        data = df.copy()
        signals = pd.DataFrame({}, columns = ['timestamp', 'signal'])
        for row in data.itertuples(index=False):
            new_row = {'timestamp': data['open_time'], 'signal':self.runner(*row)}
            signals = pd.concat([signals, pd.DataFrame([new_row])], ignore_index=True)
        
        buy_df = (signals[['signal']] == 1).astype(int)
        sell_df = (signals[['signal']] == -1).astype(int)
        target_signals = buy_df['signal'] - sell_df['signal'].fillna(0)

        data['signal'] = target_signals

        
        return data
        # data["ma"] = data["close"].rolling(window=self.rolling_window).mean()
        # data["l_bound"] = data["ma"] - self.atr * 0.5
        # data["u_bound"] = data["ma"] + self.atr * 0.5

        # bounce_indices, pen_indices = calculate_market_events(
        #     data["close"],
        #     data["l_bound"],
        #     data["u_bound"],
        #     self.rolling_window,
        # )

        # nonnegative_slope_timestamps = get_nonnegative_slope_timestamps(
        #     data["open_time"],
        #     data["u_bound"],
        #     window=self.slope_window,
        # )

        # filtered_bounce_indices = data.loc[bounce_indices, "open_time"]
        # filtered_bounce_indices = filtered_bounce_indices[
        #     filtered_bounce_indices.isin(nonnegative_slope_timestamps)
        # ].index.tolist()

        # data["bounce_event"] = 0
        # data.loc[filtered_bounce_indices, "bounce_event"] = 1

        # if self.hold_periods == 1:
        #     data["signal"] = data["bounce_event"]
        # else:
        #     data["signal"] = (
        #         data["bounce_event"]
        #         .rolling(window=self.hold_periods, min_periods=1)
        #         .max()
        #         .astype(int)
        #     )

        # data["signal"] = data["signal"].fillna(0).astype(int)
        # data["pen_event"] = 0
        # data.loc[pen_indices, "pen_event"] = 1
        # data["slope_nonnegative"] = data["open_time"].isin(nonnegative_slope_timestamps)

        # return data

    def runner(self,
        open_time,
        open,
        high,
        low,
        close,
        volume,
        close_time,
        quote_asset_volume,
        number_of_trades,
        taker_buy_base_asset_volume,
        taker_buy_quote_asset_volume,
        ignore,
    ):
        '''
        This function gets one snapshot of market data and produces buy/hold/sell <-> 1/0/-1 signal
        '''
        current_ma = self.calculator.calculate_ma(close)
        current_slope = self.calculator.calculate_slope(close)

        if current_slope:
            return self.detect_signal(current_ma, self.atr, close)
        return 0
            

    def detect_signal(self, ma, atr, price):
        above = self.above
        under = self.under
        inside = self.inside
        wait = self.wait
        signal = 0

        ubound = ma + atr / 2
        lbound = ma - atr / 2

        if not ma:
            return 0

        if not above and not under and not inside:
            if price > ubound:
                above = True
            elif price < lbound:
                under = True
            elif lbound <= price <= ubound:
                inside, wait = True, True
            signal = 0
        else:
            if not inside:
                if lbound <= price <= ubound:
                    inside = True
                    if above: return 1
                elif price > ubound:
                    above, under, inside = True, False, False
                elif price < lbound:
                    under, above, inside = True, False, False
            else:
                if lbound <= price <= ubound:
                    signal = 0
                
                elif wait:
                    wait = False
                    if price > ubound:
                        above, under, inside = True, False, False
                    elif price < lbound:
                        under, above, inside = True, False, False
                else:
                    if price > ubound:
                        if above: signal = -1
                        above, under, inside = True, False, False
                    elif price < lbound:
                        if above:
                            signal = -1
                        under, above, inside = True, False, False

        self.above, self.under, self.inside, self.wait = above, under, inside, wait
        return signal

