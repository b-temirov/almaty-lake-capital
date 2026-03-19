import numpy as np
import pandas as pd


def get_nonnegative_slope_timestamps(timestamp_series, value_series, window=75):
    """
    Return timestamps whose trailing linear slope is nonnegative.

    The slope is computed over evenly spaced 1-minute periods using the last
    `window` values from `value_series`. The returned timestamps are the values
    from `timestamp_series` aligned to the positions where that condition holds.
    """
    values = value_series if isinstance(value_series, pd.Series) else pd.Series(value_series)
    timestamps = pd.Series(np.asarray(timestamp_series), index=values.index)

    if len(timestamps) != len(values):
        raise ValueError("timestamp_series and value_series must have the same length")
    if window <= 0:
        raise ValueError("window must be positive")

    nonnegative_slope = pd.Series(False, index=values.index)
    if len(values) >= window:
        weights = np.arange(window, dtype=np.float64) - (window - 1) / 2
        value_array = values.to_numpy(dtype=np.float64, copy=False)
        valid_windows = np.convolve(
            (~np.isnan(value_array)).astype(np.int16),
            np.ones(window, dtype=np.int16),
            mode='valid'
        ) == window
        slope_numerators = np.correlate(np.nan_to_num(value_array, nan=0.0), weights, mode='valid')
        nonnegative_slope.iloc[window - 1:] = valid_windows & (slope_numerators >= 0.0)

    return pd.Index(timestamps[nonnegative_slope], name=getattr(timestamp_series, "name", None))
