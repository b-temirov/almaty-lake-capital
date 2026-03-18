from bot.data.binance_rest import BinanceRestClient
from bot.strategy.signals.sma import SMAStrategy
from bot.strategy.signals.backtester import Backtester
from datetime import datetime, timezone


client = BinanceRestClient()
start_time = int(datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
end_time = int(datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc).timestamp() * 1000)


df = client.klines_df(
    symbol="BTCUSDT", interval="1m", start_time=start_time, end_time=end_time
)

print("first kline")
print(df.head(1))

print("last kline")
print(df.tail(1))

strategy = SMAStrategy()

df_signals = strategy.generate_signals(df)
print("first kline with signals")
print(df_signals.head(1))

print("last kline with signals")
print(df_signals.tail(1))

bt = Backtester(df, strategy)
results = bt.run()

print("results of a sma backtest")
print(results)
