from datetime import datetime, timezone

from bot.backtesting.backtester import Backtester
from bot.data.historical.binance_rest import BinanceRestClient
from bot.strategies.ema import EMAStrategy


def main():
    client = BinanceRestClient()
    start_time = int(datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)

    df = client.klines_df(
        symbol="BTCUSDT",
        interval="1m",
        start_time=start_time,
        end_time=end_time,
    )

    print("first kline")
    print(df[["open_time", "close"]].head(1))

    print("last kline")
    print(df[["open_time", "close"]].tail(1))

    strategy = EMAStrategy(fast_window=20, slow_window=40)
    df_signals = strategy.generate_signals(df)

    print("first kline with EMA signals")
    print(df_signals[["open_time", "close", "ema_fast", "ema_slow", "signal"]].head(1))

    print("last kline with EMA signals")
    print(df_signals[["open_time", "close", "ema_fast", "ema_slow", "signal"]].tail(1))

    bt = Backtester(df, strategy)
    results = bt.run()

    print("results of an EMA backtest")
    print(results)


if __name__ == "__main__":
    main()
