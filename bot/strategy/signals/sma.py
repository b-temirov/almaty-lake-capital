from backtester import CryptoStrategy, Backtester
import glob
import numpy as np
import os
import pandas as pd

class SMAStrategy(CryptoStrategy):
    """Example Simple Moving Average Crossover Strategy."""
    def generate_signals(self, df):
        df['sma_fast'] = df['close'].rolling(window=10).mean()
        df['sma_slow'] = df['close'].rolling(window=50).mean()
        df['signal'] = np.where(df['sma_fast'] > df['sma_slow'], 1, 0)
        return df
    
path = f'/home/ora/Desktop/luma/almaty-lake-capital/bot/data/data/spot/daily/klines/BTCUSDT/1m/2026-01-11_2026-03-13'

all_files = glob.glob(os.path.join(path, "*.csv"))
cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
        'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 
        'taker_buy_quote_asset_volume', 'ignore']

# Load and concatenate all dataframes
dfs = []
for file in all_files:
    if os.path.exists(file):
        temp_df = pd.read_csv(file, names=cols)
        dfs.append(temp_df)

if dfs:
    full_df = pd.concat(dfs).sort_values('open_time').reset_index(drop=True)

    # Check first value to decide unit (ns vs ms)
    first_ts = full_df['open_time'].iloc[0]
    ts_unit = 'ns' if len(str(int(first_ts))) >= 16 else 'ms'

    # Convert time to datetime
    full_df['open_time'] = pd.to_datetime(full_df['open_time'], unit=ts_unit)

    # Initialize Strategy and Backtester with the updated class definition
    strategy = SMAStrategy()
    bt = Backtester(full_df, strategy)

    # Run Backtest
    results = bt.run()

    print(f"Backtest Results on Uploaded Data (Unit: {ts_unit}):")
    for metric, value in results.items():
        print(f'{metric}: {value:.4f}')

    # Display first few rows of equity curve
    print(bt.data[['open_time', 'close', 'signal', 'equity_curve']].tail())

    # Now that 'bt' is refreshed, this will visualize the results
    if 'bt' in globals():
        bt.plot_results()
    else:
        print("Backtester instance 'bt' not found.")
else:
    print("No files found. Please ensure the CSVs are uploaded to the /content/ directory.")