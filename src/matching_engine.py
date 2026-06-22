"""
matching_engine.py
Processes incoming orders against the OrderBook, generating trades.

Matching rule: price-time priority.
- A BUY order matches against the lowest-priced SELL orders first.
- A SELL order matches against the highest-priced BUY orders first.
- Within the same price level, the earliest-arrived order fills first (FIFO).
- Trade price = the RESTING order's price (the order already sitting in the
  book), since that order's price was already public/committed first.

Optional portfolio integration:
  Pass `portfolio` and `ticker` to process_order so the engine can credit
  fills to the player's virtual account.  Bot orders skip portfolio updates.
"""

import itertools
from typing import Optional
from .order import Order, Trade, Side, OrderType
from .order_book import OrderBook

_trade_id_seq = itertools.count(1)


class MatchingEngine:
    def __init__(self):
        self.book = OrderBook()
        self.trades: list[Trade] = []

    def process_order(
        self,
        order: Order,
        portfolio=None,   # src.portfolio.Portfolio | None
        ticker: str = "",
        is_player_order: bool = False,
    ) -> list[Trade]:
        """
        Match an incoming order against the book; rest any unfilled LIMIT remainder.

        If `portfolio` and `is_player_order` are supplied, fills are applied to the
        portfolio so cash / position are updated in real time.
        """
        new_trades = []
        opposite_side = Side.SELL if order.side == Side.BUY else Side.BUY

        while order.remaining > 0:
            best_price = self.book.best_price(opposite_side)
            if best_price is None:
                break  # no liquidity available on the other side

            if order.order_type == OrderType.LIMIT:
                crosses = (order.price >= best_price) if order.side == Side.BUY \
                    else (order.price <= best_price)
                if not crosses:
                    break  # best opposite price isn't good enough for this limit order

            level = self.book.levels_for(opposite_side)[best_price]

            while level and order.remaining > 0:
                resting = level[0]
                if resting.cancelled or resting.is_filled():
                    level.popleft()
                    continue

                fill_qty = min(order.remaining, resting.remaining)
                order.remaining -= fill_qty
                resting.remaining -= fill_qty

                buy_id = order.order_id if order.side == Side.BUY else resting.order_id
                sell_id = order.order_id if order.side == Side.SELL else resting.order_id

                trade = Trade(
                    trade_id=next(_trade_id_seq),
                    buy_order_id=buy_id,
                    sell_order_id=sell_id,
                    price=best_price,
                    quantity=fill_qty,
                    seq=order.arrival_seq,
                )
                new_trades.append(trade)

                # Credit the fill to the player's portfolio if this is their order
                if is_player_order and portfolio is not None and ticker:
                    portfolio.apply_fill(trade, order.side, ticker)

                if resting.is_filled():
                    level.popleft()

            if not level:
                self.book.levels_for(opposite_side).pop(best_price, None)

        # Any unfilled remainder:
        if order.remaining > 0 and order.order_type == OrderType.LIMIT:
            self.book.add_resting_order(order)
            # Track open order in portfolio if player order
            if is_player_order and portfolio is not None and ticker:
                portfolio.register_order(order, ticker)
        elif is_player_order and portfolio is not None:
            # Fully filled or market order — ensure it's not in open orders
            portfolio.remove_open_order(order.order_id)

        # MARKET orders never rest — an unfilled remainder is simply dropped.
        self.trades.extend(new_trades)
        return new_trades
