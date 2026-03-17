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
    def server_time(self):
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

    # ---------- Pair metadata / validation ----------
    def get_pair_info(self, pair: str) -> Dict[str, Any]:
        info = self.exchange_info()
        trade_pairs = info.get("TradePairs", {})
        if pair not in trade_pairs:
            raise ValueError(f"Unknown trading pair: {pair}")
        return trade_pairs[pair]

    def _round_to_precision(self, value: float, precision: int) -> float:
        q = Decimal("1") if precision == 0 else Decimal("1." + "0" * precision)
        return float(Decimal(str(value)).quantize(q, rounding=ROUND_DOWN))

    def round_quantity(self, pair: str, quantity: float) -> float:
        pair_info = self.get_pair_info(pair)
        precision = int(pair_info["AmountPrecision"])
        return self._round_to_precision(quantity, precision)

    def round_price(self, pair: str, price: float) -> float:
        pair_info = self.get_pair_info(pair)
        precision = int(pair_info["PricePrecision"])
        return self._round_to_precision(price, precision)

    def validate_order(
        self, pair: str, quantity: float, price: Optional[float] = None
    ) -> None:
        pair_info = self.get_pair_info(pair)

        if not pair_info.get("CanTrade", False):
            raise ValueError(f"Pair {pair} is not tradable")

        min_order = float(pair_info["MiniOrder"])
        if quantity < min_order:
            raise ValueError(f"Quantity {quantity} is below MiniOrder {min_order}")

        rounded_qty = self.round_quantity(pair, quantity)
        if rounded_qty != quantity:
            raise ValueError(
                f"Quantity {quantity} does not match AmountPrecision; try {rounded_qty}"
            )

        if price is not None:
            rounded_price = self.round_price(pair, price)
            if rounded_price != price:
                raise ValueError(
                    f"Price {price} does not match PricePrecision; try {rounded_price}"
                )

    # ---------- Orders ----------

    def place_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        validate: bool = True,
    ) -> Dict[str, Any]:
        side = side.upper()
        order_type = order_type.upper()

        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")

        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError("order_type must be MARKET or LIMIT")

        if order_type == "LIMIT" and price is None:
            raise ValueError("LIMIT order requires price")

        if order_type == "MARKET" and price is not None:
            raise ValueError("MARKET order should not include price")

        if validate:
            self.validate_order(pair, quantity, price)

        data = {
            "pair": pair,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if order_type == "LIMIT":
            data["price"] = price

        return self._post("/v3/place_order", data=data, signed=True)

    def market_buy(self, pair: str, quantity: float) -> Dict[str, Any]:
        return self.place_order(
            pair=pair, side="BUY", order_type="MARKET", quantity=quantity
        )

    def market_sell(self, pair: str, quantity: float) -> Dict[str, Any]:
        return self.place_order(
            pair=pair, side="SELL", order_type="MARKET", quantity=quantity
        )

    def limit_buy(self, pair: str, quantity: float, price: float) -> Dict[str, Any]:
        return self.place_order(
            pair=pair, side="BUY", order_type="LIMIT", quantity=quantity, price=price
        )

    def limit_sell(self, pair: str, quantity: float, price: float) -> Dict[str, Any]:
        return self.place_order(
            pair=pair, side="SELL", order_type="LIMIT", quantity=quantity, price=price
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
