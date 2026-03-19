from bot.data.streaming.binance_ws import BinanceWebSocketClient

client = BinanceWebSocketClient()

count = 0
for df in client.stream_klines_df(symbol="BTCUSDT", interval="1m", closed_only=True):
    print(df[["open_time", "close", "volume", "is_closed"]])
    count += 1
    if count == 3:
        break
