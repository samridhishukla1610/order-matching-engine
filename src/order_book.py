"""
order_book.py
A limit order book using price-time priority.

Design notes (good interview talking points):
- Bids are stored in a max-heap (Python's heapq is min-heap only, so prices are negated).
- Asks are stored in a min-heap.
- Each price level holds a deque of orders in arrival order (FIFO) -> O(1) append/popleft.
- "Lazy deletion": when a price level's deque empties out, it is NOT removed from the
  heap immediately (heapq doesn't support efficient arbitrary removal, only O(log n)
  push/pop of the top). Instead, stale levels are cleaned up the next time that price
  would become the best price. This keeps every operation O(log n) amortized instead
  of O(n) for a naive "remove from middle" approach.
"""

import heapq
from collections import deque
from .order import Order, Side


class OrderBook:
    def __init__(self):
        self.bid_heap = []      # stores NEGATED prices (max-heap behavior)
        self.ask_heap = []      # stores prices as-is (min-heap behavior)
        self.bid_levels = {}    # price -> deque[Order]
        self.ask_levels = {}    # price -> deque[Order]
        self.orders_by_id = {}  # order_id -> Order, used for cancellation lookups

    # ---------- internal helpers (still used by MatchingEngine) ----------

    def levels_for(self, side: Side) -> dict:
        return self.bid_levels if side == Side.BUY else self.ask_levels

    def heap_for(self, side: Side) -> list:
        return self.bid_heap if side == Side.BUY else self.ask_heap

    # ---------- public API ----------

    def best_price(self, side: Side):
        """Peek the best (highest bid / lowest ask) price that still has live orders."""
        heap = self.heap_for(side)
        levels = self.levels_for(side)
        while heap:
            top = heap[0]
            price = -top if side == Side.BUY else top
            level = levels.get(price)
            if level and len(level) > 0:
                return price
            # stale / empty level sitting at the top of the heap -> lazily drop it
            heapq.heappop(heap)
            levels.pop(price, None)
        return None

    def add_resting_order(self, order: Order):
        """Add an order that didn't fully match — it rests in the book waiting for a counterparty."""
        levels = self.levels_for(order.side)
        heap = self.heap_for(order.side)
        if order.price not in levels:
            levels[order.price] = deque()
            heapq.heappush(heap, -order.price if order.side == Side.BUY else order.price)
        levels[order.price].append(order)
        self.orders_by_id[order.order_id] = order

    def cancel(self, order_id: int) -> bool:
        """
        Mark a resting order as cancelled. It is left in place in its deque (lazy
        deletion, same idea as the heap) and simply skipped over the next time the
        matching engine reaches it.
        """
        order = self.orders_by_id.get(order_id)
        if order is None or order.is_filled() or order.cancelled:
            return False
        order.cancelled = True
        return True

    def depth(self, levels_count: int = 5):
        """
        Return the top N price levels on each side for display, without mutating
        the real heaps: [(price, total_live_qty), ...] sorted best-price-first.
        """

        def snapshot(side):
            heap = list(self.heap_for(side))
            heapq.heapify(heap)
            levels = self.levels_for(side)
            result = []
            while heap and len(result) < levels_count:
                top = heapq.heappop(heap)
                price = -top if side == Side.BUY else top
                level = levels.get(price)
                if level:
                    qty = sum(o.remaining for o in level if not o.cancelled)
                    if qty > 0:
                        result.append((price, qty))
            return result

        return snapshot(Side.BUY), snapshot(Side.SELL)
