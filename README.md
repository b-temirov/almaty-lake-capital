# ALC (Almaty Lake Capital) Trading Bot

This repository contains the trading bot developed by Team ALC for the SG vs HK University Web3 Quant Hackathon.

## Setup
Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Core Idea
The project follows a simple flow:

1. Fetch klines as a pandas DataFrame.
2. Pass that DataFrame into a strategy.
3. Let the strategy add a `signal` column.
4. Run the backtester on that DataFrame and strategy.

## Fetch Market Data
Use `BinanceRestClient.klines_df()` to load candles for any symbol, interval, and time period.

```python
from bot.data.binance_rest import BinanceRestClient

client = BinanceRestClient()
df = client.klines_df(
    symbol="BTCUSDT",
    interval="1h",
    start_time=...,
    end_time=...,
)
```

`df` is a pandas DataFrame where each row is one kline.

## Create a Strategy
A strategy should implement one method:

```python
generate_signals(df)
```

It takes a DataFrame of klines and returns a DataFrame with a `signal` column added.

Example:

```python
from bot.strategy.signals.sma import SMAStrategy

strategy = SMAStrategy(fast_window=10, slow_window=50)
signal_df = strategy.generate_signals(df)
```

You can use `generate_signals(df)` by itself to inspect signals without running a backtest.

## Run a Backtest
Initialize the backtester with the DataFrame and strategy, then call `run()`:

```python
from bot.strategy.signals.backtester import Backtester

bt = Backtester(df, strategy)
results = bt.run()
```

`results` contains:

- `Total Return`
- `Sharpe Ratio`
- `Sortino Ratio`
- `Calmar Ratio`
- `Max Drawdown`

## Full Example

```python
from bot.data.binance_rest import BinanceRestClient
from bot.strategy.signals.sma import SMAStrategy
from bot.strategy.signals.backtester import Backtester

client = BinanceRestClient()
df = client.klines_df(
    symbol="BTCUSDT",
    interval="1h",
    start_time=...,
    end_time=...,
)

strategy = SMAStrategy(fast_window=10, slow_window=50)
bt = Backtester(df, strategy)
results = bt.run()

print(results)
```

## Running Tests
Run tests from the repository root:

```bash
python3 -m tests.binance_rest_test
python3 -m tests.sma_strategy_test
```
