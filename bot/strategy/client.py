import time
import hmac
import hashlib
import requests
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional


class RoostooClient:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://mock-api.roostoo.com",
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.session = requests.Session()
        self._exchange_info_cache = None

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        query_string = "&".join(
            f"{k}={v}" for k, v in sorted(params.items()) if v is not None
        )
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_headers(self, params):
        return {
            "RST-API-KEY": self.api_key,
            "MSG-SIGNATURE": self._sign(params),
        }

    def _get(self, path, params=None, signed=False):
        params = dict(params or {})

        if signed:
            params.setdefault("timestamp", self._timestamp())

        headers = self._signed_headers(params) if signed else {}

        resp = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, data, signed=True):
        payload = dict(data)
        payload.setdefault("timestamp", self._timestamp())
        headers = self._signed_headers(payload) if signed else {}
        resp = self.session.post(
            f"{self.base_url}{path}",
            data=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    # ---------- Public endpoints ----------
    def server_time(self):  # add validation
        return self._get(path="/v3/serverTime")

    def exchange_info(self, refresh=False):
        if self._exchange_info_cache is None or refresh:
            self._exchange_info_cache = self._get(path="/v3/exchangeInfo")
        return self._exchange_info_cache

    def ticker(self, pair=None):
        params = {"timestamp": self._timestamp()}
        if pair is not None:
            params["pair"] = pair
        return self._get(path="/v3/ticker", params=params)

    # ---------- Account ----------
    def balance(self):
        return self._get("/v3/balance", signed=True)

    # ---------- Coin metadata / validation ----------
    def get_coin_info(self, coin):
        info = self.exchange_info()

        if not info.get("IsRunning", False):
            raise ValueError("Exchange is not running")

        trade_pairs = info.get("TradePairs", {})
        key = f"{coin.upper()}/USD"
        if key not in trade_pairs:
            raise ValueError(f"Unknown coin: {coin}")
        return trade_pairs[key]

    def _round_to_precision(self, value: float, precision: int) -> float:
        q = Decimal("1") if precision == 0 else Decimal("1." + "0" * precision)
        return float(Decimal(str(value)).quantize(q, rounding=ROUND_DOWN))

    def free_balance(self, asset):
        wallet = self.balance().get("SpotWallet", {})
        asset_info = wallet.get(asset.upper(), {})
        return float(asset_info.get("Free", 0))

    def fee_rate(self, order_type):
        order_type = order_type.upper()
        if order_type == "MARKET":
            return 0.001
        if order_type == "LIMIT":
            return 0.0005
        raise ValueError("order_type must be MARKET or LIMIT")

    def round_quantity(self, coin, quantity):
        coin_info = self.get_coin_info(coin)
        precision = int(coin_info["AmountPrecision"])
        return self._round_to_precision(quantity, precision)

    def round_price(self, coin, price):
        coin_info = self.get_coin_info(coin)
        precision = int(coin_info["PricePrecision"])
        return self._round_to_precision(price, precision)

    def validate_order(self, coin, side, order_type, quantity, price=None):
        coin = coin.upper()
        side = side.upper()
        order_type = order_type.upper()

        coin_info = self.get_coin_info(coin)

        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")

        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError("order_type must be MARKET or LIMIT")

        if order_type == "LIMIT" and price is None:
            raise ValueError("LIMIT order requires price")

        if order_type == "MARKET" and price is not None:
            raise ValueError("MARKET order should not include price")

        if not coin_info.get("CanTrade", False):
            raise ValueError(f"coin {coin} is not tradable")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")

        rounded_qty = self.round_quantity(coin, quantity)
        if Decimal(str(rounded_qty)) != Decimal(str(quantity)):
            raise ValueError(
                f"Quantity {quantity} does not match AmountPrecision; try {rounded_qty}"
            )

        if order_type == "LIMIT":
            if price is None or price <= 0:
                raise ValueError("LIMIT order requires price > 0")

            rounded_price = self.round_price(coin, price)
            if Decimal(str(rounded_price)) != Decimal(str(price)):
                raise ValueError(
                    f"Price {price} does not match PricePrecision; try {rounded_price}"
                )

            effective_price = price

        elif order_type == "MARKET":
            ticker = self.ticker(f"{coin}/USD")
            pair_data = ticker["Data"][f"{coin}/USD"]

            if side == "BUY":
                effective_price = float(pair_data["MinAsk"])
            else:
                effective_price = float(pair_data["MaxBid"])

        else:
            raise ValueError("order_type must be LIMIT or MARKET")

        min_order = float(coin_info["MiniOrder"])
        notional = effective_price * quantity

        if notional <= min_order:
            raise ValueError(f"Order value {notional} is below MiniOrder {min_order}")

        fee_rate = self.fee_rate(order_type)

        if side == "BUY":
            usd_free = self.free_balance("USD")
            required_usd = notional * (1 + fee_rate)
            if usd_free < required_usd:
                raise ValueError(
                    f"Insufficient USD balance: need {required_usd}, have {usd_free}"
                )

        elif side == "SELL":
            coin_free = self.free_balance(coin)
            if coin_free < quantity:
                raise ValueError(
                    f"Insufficient {coin} balance: need {quantity}, have {coin_free}"
                )

        else:
            raise ValueError("side must be BUY or SELL")

    # ---------- Orders ----------
    def place_order(self, coin, side, order_type, quantity, price=None):
        side = side.upper()
        order_type = order_type.upper()
        coin = coin.upper()

        self.validate_order(coin, side, order_type, quantity, price)

        data = {
            "pair": coin + "/USD",
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if order_type == "LIMIT":
            data["price"] = price

        return self._post("/v3/place_order", data=data, signed=True)

    def market_buy(self, coin, quantity):
        return self.place_order(
            coin=coin, side="BUY", order_type="MARKET", quantity=quantity
        )

    def market_sell(self, coin, quantity):
        return self.place_order(
            coin=coin, side="SELL", order_type="MARKET", quantity=quantity
        )

    def limit_buy(self, coin, quantity, price):
        return self.place_order(
            coin=coin, side="BUY", order_type="LIMIT", quantity=quantity, price=price
        )

    def limit_sell(self, coin, quantity, price):
        return self.place_order(
            coin=coin, side="SELL", order_type="LIMIT", quantity=quantity, price=price
        )

    def query_order(
        self,
        order_id: Optional[int] = None,
        pair: Optional[str] = None,
        pending_only: Optional[bool] = None,
    ) -> Dict[str, Any]:
        data = {
            "order_id": order_id,
            "pair": pair,
            "pending_only": pending_only,
        }
        return self._post("/v3/query_order", data=data, signed=True)

    def cancel_order(
        self,
        order_id: Optional[int] = None,
        pair: Optional[str] = None,
    ) -> Dict[str, Any]:
        if order_id is None and pair is None:
            raise ValueError("Provide at least order_id or pair")
        data = {
            "order_id": order_id,
            "pair": pair,
        }
        return self._post("/v3/cancel_order", data=data, signed=True)

    def pending_count(self, pair: Optional[str] = None) -> Dict[str, Any]:
        params = {"pair": pair} if pair else {}
        return self._get("/v3/pending_count", params=params, signed=True)
