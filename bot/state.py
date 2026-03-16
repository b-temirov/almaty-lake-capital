# from types import SimpleNamespace
from typing import Dict
from .types import MarketState, TickerData, Balance, ExchangePairRule


class StateCollector:
    def __init__(self, client):
        self.client = client
        self._pair_rules_cache: Dict[str, ExchangePairRule] = {}

    def load_exchange_rules(self) -> Dict[str, ExchangePairRule]:
        raw = self.client.exchange_info()
        trade_pairs = raw.get("TradePairs", {})
        rules = {}
        for pair, info in trade_pairs.items():
            rules[pair] = ExchangePairRule(
                pair=pair,
                price_precision=info["PricePrecision"],
                amount_precision=info["AmountPrecision"],
                min_order=float(info["MiniOrder"]),
                can_trade=bool(info["CanTrade"]),
            )
        self._pair_rules_cache = rules
        return rules

    def collect(self) -> MarketState:
        if not self._pair_rules_cache:
            self.load_exchange_rules()

        ticker_raw = self.client.ticker()
        balance_raw = self.client.balance()

        tickers = self._parse_tickers(ticker_raw)
        balances = self._parse_balances(balance_raw)

        # query_order API details may vary in shape; adapt parser after you inspect responses
        open_orders = []

        return MarketState(
            ts=self.client._timestamp(),
            tickers=tickers,
            balances=balances,
            open_orders=open_orders,
            pair_rules=self._pair_rules_cache,
            features={},
        )

    def _parse_tickers(self, raw):
        tickers = {}
        for pair, item in raw.items():
            if not isinstance(item, dict):
                continue
            bid = float(item.get("Bid", item.get("bid", 0)))
            ask = float(item.get("Ask", item.get("ask", 0)))
            last = float(item.get("Close", item.get("Last", item.get("last", 0))))
            tickers[pair] = TickerData(pair=pair, bid=bid, ask=ask, last=last, raw=item)
        return tickers

    def _parse_balances(self, raw):
        balances = {}
        for asset, amount in raw.items():
            balances[asset] = Balance(asset=asset, free=float(amount))
        return balances
