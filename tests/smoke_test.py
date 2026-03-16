import os
import json
from bot.client import RoostooClient
from dotenv import load_dotenv


load_dotenv()


def pretty(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, indent=2, sort_keys=True))


def main():
    client = RoostooClient(
        api_key=os.environ["ROOSTOO_API_KEY"],
        secret_key=os.environ["ROOSTOO_SECRET_KEY"],
    )

    # 1. No-auth test
    server_time = client.server_time()
    pretty("server_time", server_time)

    # 2. No-auth test
    exchange_info = client.exchange_info()
    pretty("exchange_info", exchange_info)

    # 3. Signed test
    balance = client.balance()
    pretty("balance", balance)


if __name__ == "__main__":
    main()
