# test.py
import os
from pprint import pprint
from bot.strategy.client import RoostooClient
from dotenv import load_dotenv


load_dotenv()


def main():
    # Public endpoints do not require valid keys for basic testing on the mock API,
    # but we still pass placeholder strings because the client constructor expects them.
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
    #     result = client.ticker()
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
        print(f"ticker(single pair) failed: {e}")


if __name__ == "__main__":
    main()
