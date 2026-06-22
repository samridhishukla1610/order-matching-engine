"""
portfolio.py
Tracks a single player's virtual cash balance, share positions, open orders,
and trade history.  All money is fake — this is a paper-trading simulator.
"""

from dataclasses import dataclass, field
from typing import Optional
from .order import Order, Trade, Side


STARTING_CASH: float = 1_00_000.0  # ₹1,00,000 virtual cash


@dataclass
class PortfolioTrade:
    """A filled trade from the player's perspective."""
    trade_id: int
    ticker: str
    side: str          # "BUY" or "SELL"
    price: float
    quantity: int
    cash_impact: float  # negative for buys, positive for sells


@dataclass
class Portfolio:
    cash: float = STARTING_CASH
    positions: dict = field(default_factory=dict)   # ticker -> int (shares held)
    open_orders: dict = field(default_factory=dict) # order_id -> Order
    trade_history: list = field(default_factory=list)  # list[PortfolioTrade]

    # ------------------------------------------------------------------ #
    # Order tracking
    # ------------------------------------------------------------------ #

    def register_order(self, order: Order, ticker: str):
        """Record a newly submitted order as open."""
        self.open_orders[order.order_id] = (order, ticker)

    def remove_open_order(self, order_id: int):
        self.open_orders.pop(order_id, None)

    # ------------------------------------------------------------------ #
    # Fill processing
    # ------------------------------------------------------------------ #

    def apply_fill(self, trade: Trade, player_side: Side, ticker: str):
        """
        Called by the engine whenever the player's order participates in a trade.
        Updates cash and position accordingly.
        """
        cost = trade.price * trade.quantity

        if player_side == Side.BUY:
            self.cash -= cost
            self.positions[ticker] = self.positions.get(ticker, 0) + trade.quantity
            cash_impact = -cost
            side_str = "BUY"
        else:
            self.cash += cost
            self.positions[ticker] = self.positions.get(ticker, 0) - trade.quantity
            cash_impact = cost
            side_str = "SELL"

        self.trade_history.append(PortfolioTrade(
            trade_id=trade.trade_id,
            ticker=ticker,
            side=side_str,
            price=trade.price,
            quantity=trade.quantity,
            cash_impact=cash_impact,
        ))

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def can_afford(self, price: float, quantity: int) -> bool:
        """Check whether the player has enough cash to place a buy limit order."""
        return self.cash >= price * quantity

    def has_position(self, ticker: str, quantity: int) -> bool:
        """Check whether the player holds enough shares to place a sell order."""
        return self.positions.get(ticker, 0) >= quantity

    # ------------------------------------------------------------------ #
    # Derived stats
    # ------------------------------------------------------------------ #

    def position_value(self, ticker: str, last_price: Optional[float]) -> float:
        """Mark-to-market value of the position in a single ticker."""
        if last_price is None:
            return 0.0
        return self.positions.get(ticker, 0) * last_price

    def total_equity(self, prices: dict) -> float:
        """Cash + mark-to-market value of all positions."""
        pos_value = sum(
            qty * prices.get(ticker, 0)
            for ticker, qty in self.positions.items()
        )
        return self.cash + pos_value

    def realized_pnl(self) -> float:
        return sum(t.cash_impact for t in self.trade_history)
