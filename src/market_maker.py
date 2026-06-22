"""
market_maker.py
A simple algorithmic market maker that continuously posts bid/ask quotes
around a drifting mid price.  This keeps the book alive so the player
always has liquidity to trade against.

Strategy: basic symmetric quoting
  - Post N bid levels below mid, N ask levels above mid
  - Each level is `spread_step` apart
  - Quantities are randomised within a range
  - Mid price does a random walk each tick
"""

import random
from .order import Order, Side, OrderType
from .matching_engine import MatchingEngine


class MarketMaker:
    def __init__(
        self,
        mid_price: float = 100.0,
        spread_step: float = 0.25,
        levels: int = 5,
        qty_min: int = 5,
        qty_max: int = 30,
        drift_sigma: float = 0.10,   # std-dev of per-tick mid-price random walk
    ):
        self.mid_price = mid_price
        self.spread_step = spread_step
        self.levels = levels
        self.qty_min = qty_min
        self.qty_max = qty_max
        self.drift_sigma = drift_sigma

    def tick(self, engine: MatchingEngine):
        """
        Post one round of quotes.  The mid price drifts slightly each tick
        to simulate a live market.
        """
        # Random walk on mid price
        self.mid_price += random.gauss(0, self.drift_sigma)
        self.mid_price = max(1.0, round(self.mid_price, 2))

        for i in range(1, self.levels + 1):
            bid_price = round(self.mid_price - i * self.spread_step, 2)
            ask_price = round(self.mid_price + i * self.spread_step, 2)
            qty = random.randint(self.qty_min, self.qty_max)

            engine.process_order(Order(
                side=Side.BUY,
                price=bid_price,
                quantity=qty,
                order_type=OrderType.LIMIT,
            ))
            engine.process_order(Order(
                side=Side.SELL,
                price=ask_price,
                quantity=qty,
                order_type=OrderType.LIMIT,
            ))

    def current_mid(self) -> float:
        return self.mid_price
