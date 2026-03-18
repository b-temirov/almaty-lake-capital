# test.py
import os
from pprint import pprint
from bot.logging_config import setup_logging
from bot.execution.roostoo_client import RoostooClient
from dotenv import load_dotenv


load_dotenv()
setup_logging()


def main():
    client = RoostooClient(
        api_key=os.environ["ROOSTOO_API_KEY"],
        secret_key=os.environ["ROOSTOO_SECRET_KEY"],
    )

    # print("\n=== 1) server_time() ===")
    # try:
    #     result = client.server_time()
    #     pprint(result)
    # except Exception as e:
    #     print(f"server_time failed: {e}")

    # print("\n=== 2) exchange_info() ===")
    # try:
    #     result = client.exchange_info()
    #     pprint(result)
    # except Exception as e:
    #     print(f"exchange_info failed: {e}")

    # print("\n=== 3) ticker() -> all pairs ===")
    # try:
    #     result = client.ticker("BTC/USD")
    #     pprint(result)
    # except Exception as e:
    #     print(f"ticker(all) failed: {e}")

    # print("\n=== 4) ticker(pair='BTC/USD') ===")
    # try:
    #     result = client.ticker(pair="BTC/USD")
    #     pprint(result)
    # except Exception as e:
    #     print(f"ticker(single pair) failed: {e}")

    print("\n=== 5) balance ===")
    try:
        result = client.balance()
        pprint(result)
    except Exception as e:
        print(f"balance failed: {e}")

    # print("\n=== 6) market_buy('DOGE', 20) ===")
    # try:
    #     result = client.market_buy("DOGE", 20)
    #     pprint(result)
    # except Exception as e:
    #     print(f"market_buy failed: {e}")

    # print("\n=== 7) market_sell('DOGE', 20) ===")
    # try:
    #     result = client.market_sell("DOGE", 20)
    #     pprint(result)
    # except Exception as e:
    #     print(f"market_sell failed: {e}")

    # some_price_below_market = 0.09880
    # some_price_above_market = 0.09900

    # print("\n=== 8) limit_buy('DOGE', 20, some_price_below_market) ===")
    # try:
    #     result = client.limit_buy("DOGE", 20, some_price_below_market)
    #     pprint(result)
    # except Exception as e:
    #     print(f"limit_buy failed: {e}")

    # print("\n=== 9) limit_sell('DOGE', 10, some_price_above_market) ===")
    # try:
    #     result = client.limit_sell("DOGE", 10, some_price_above_market)
    #     pprint(result)
    # except Exception as e:
    #     print(f"limit_sell failed: {e}")


if __name__ == "__main__":
    main()
