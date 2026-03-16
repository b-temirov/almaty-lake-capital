import time
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional

class RoostooClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://mock-api.roostoo.com", timeout: int = 10):
        self.api_key = api_key
        self.secret_key = secret_key.encode()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _canonical_string(self, params: Dict[str, Any]) -> str:
        items = sorted((k, str(v)) for k, v in params.items() if v is not None)
        return "&".join(f"{k}={v}" for k, v in items)

    def _sign(self, params: Dict[str, Any]) -> str:
        payload = self._canonical_string(params)
        return hmac.new(self.secret_key, payload.encode(), hashlib.sha256).hexdigest()

    def _signed_headers(self, params: Dict[str, Any]) -> Dict[str, str]:
        return {
            "RST-API-KEY": self.api_key,
            "MSG-SIGNATURE": self._sign(params),
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Dict[str, Any]:
        params = dict(params or {})
        if signed or path.endswith("/ticker"):
            params.setdefault("timestamp", self._timestamp())

        headers = self._signed_headers(params) if signed else {}
        resp = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: Dict[str, Any], signed: bool = True) -> Dict[str, Any]:
        payload = dict(data)
        payload.setdefault("timestamp", self._timestamp())
        headers = self._signed_headers(payload) if signed else {}
        resp = self.session.post(
            f"{self.base_url}{path}",
            data=payload,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def server_time(self):
        return self._get("/v3/serverTime", signed=False)

    def exchange_info(self):
        return self._get("/v3/exchangeInfo", signed=False)

    def ticker(self, pair: Optional[str] = None):
        params = {"pair": pair} if pair else {}
        return self._get("/v3/ticker", params=params, signed=False)

    def balance(self):
        return self._get("/v3/balance", signed=True)

    def pending_count(self, pair: Optional[str] = None):
        params = {"pair": pair} if pair else {}
        return self._get("/v3/pending_count", params=params, signed=True)

    def place_order(self, pair: str, side: str, order_type: str, quantity: float, price: Optional[float] = None):
        data = {
            "pair": pair,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if order_type == "LIMIT":
            data["price"] = price
        return self._post("/v3/place_order", data=data, signed=True)

    def query_order(self, **kwargs):
        return self._post("/v3/query_order", data=kwargs, signed=True)

    def cancel_order(self, **kwargs):
        return self._post("/v3/cancel_order", data=kwargs, signed=True)