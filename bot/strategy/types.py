from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, List, Any

Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]
Action = Literal["BUY", "SELL", "HOLD"]


@dataclass
class TickerData:
    pair: str
    bid: float
    ask: float
    last: float
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Balance:
    asset: str
    free: float


@dataclass
class ExchangePairRule:
    pair: str
    price_precision: int
    amount_precision: int
    min_order: float
    can_trade: bool


@dataclass
class OpenOrder:
    order_id: str
    pair: str
    side: Side
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketState:
    ts: int
    tickers: Dict[str, TickerData]
    balances: Dict[str, Balance]
    open_orders: List[OpenOrder]
    pair_rules: Dict[str, ExchangePairRule]
    features: Dict[str, float] = field(default_factory=dict)


@dataclass
class TradeIntent:
    action: Action
    pair: Optional[str] = None
    side: Optional[Side] = None
    order_type: Optional[OrderType] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    reason: str = ""


@dataclass
class ExecutionResult:
    accepted: bool
    order_id: Optional[str]
    message: str
    raw: Dict[str, Any] = field(default_factory=dict)
