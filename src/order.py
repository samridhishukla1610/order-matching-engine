"""
order.py
Core data structures for the limit order book matching engine.
"""

from dataclasses import dataclass, field
from enum import Enum
import itertools
import time

_order_id_seq = itertools.count(1)
_arrival_seq = itertools.count(1)


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


@dataclass
class Order:
    side: Side
    price: float                 # ignored for MARKET orders
    quantity: int
    order_type: OrderType = OrderType.LIMIT
    order_id: int = field(default_factory=lambda: next(_order_id_seq))
    # arrival_seq is a monotonically increasing counter used as the "time" in
    # price-time priority. Using a sequence number instead of a wall-clock
    # timestamp keeps matching deterministic and easy to test.
    arrival_seq: int = field(default_factory=lambda: next(_arrival_seq))
    remaining: int = field(default=None)
    cancelled: bool = False

    def __post_init__(self):
        if self.remaining is None:
            self.remaining = self.quantity

    def is_filled(self) -> bool:
        return self.remaining <= 0


@dataclass
class Trade:
    trade_id: int
    buy_order_id: int
    sell_order_id: int
    price: float
    quantity: int
    seq: int
    timestamp: float = field(default_factory=time.time)  # wall-clock time for charting
