"""
test_order_book.py
Correctness tests for the matching engine.
Run with: pytest tests/test_order_book.py
      or: python tests/test_order_book.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.order import Order, Side, OrderType
from src.matching_engine import MatchingEngine


def test_no_match_when_prices_dont_cross():
    engine = MatchingEngine()
    engine.process_order(Order(side=Side.BUY, price=100, quantity=10))
    engine.process_order(Order(side=Side.SELL, price=101, quantity=10))
    assert len(engine.trades) == 0
    bids, asks = engine.book.depth()
    assert bids == [(100, 10)]
    assert asks == [(101, 10)]


def test_simple_match():
    engine = MatchingEngine()
    engine.process_order(Order(side=Side.BUY, price=100, quantity=10))
    trades = engine.process_order(Order(side=Side.SELL, price=100, quantity=10))
    assert len(trades) == 1
    assert trades[0].price == 100
    assert trades[0].quantity == 10
    bids, asks = engine.book.depth()
    assert bids == []
    assert asks == []


def test_partial_fill_leaves_remainder_resting():
    engine = MatchingEngine()
    engine.process_order(Order(side=Side.BUY, price=100, quantity=10))
    trades = engine.process_order(Order(side=Side.SELL, price=100, quantity=4))
    assert len(trades) == 1
    assert trades[0].quantity == 4
    bids, _ = engine.book.depth()
    assert bids == [(100, 6)]  # 6 units left resting on the bid side


def test_time_priority_fifo_within_same_price():
    engine = MatchingEngine()
    first = Order(side=Side.BUY, price=100, quantity=5)
    second = Order(side=Side.BUY, price=100, quantity=5)
    engine.process_order(first)
    engine.process_order(second)
    trades = engine.process_order(Order(side=Side.SELL, price=100, quantity=5))
    assert len(trades) == 1
    assert trades[0].buy_order_id == first.order_id  # earliest order at this price fills first


def test_price_priority_beats_time_priority():
    engine = MatchingEngine()
    engine.process_order(Order(side=Side.BUY, price=99, quantity=5))     # arrives first, worse price
    better = Order(side=Side.BUY, price=101, quantity=5)                  # arrives second, better price
    engine.process_order(better)
    trades = engine.process_order(Order(side=Side.SELL, price=99, quantity=5))
    assert trades[0].buy_order_id == better.order_id  # higher bid wins regardless of arrival order


def test_cancelled_order_is_skipped_during_matching():
    engine = MatchingEngine()
    resting = Order(side=Side.BUY, price=100, quantity=10)
    engine.process_order(resting)
    assert engine.book.cancel(resting.order_id) is True
    trades = engine.process_order(Order(side=Side.SELL, price=100, quantity=10))
    assert len(trades) == 0  # cancelled order must not fill


def test_market_order_does_not_rest_in_book():
    engine = MatchingEngine()
    trades = engine.process_order(
        Order(side=Side.BUY, price=0, quantity=10, order_type=OrderType.MARKET)
    )
    assert trades == []          # no liquidity to match against yet
    bids, _ = engine.book.depth()
    assert bids == []             # unfilled market order is dropped, never rests


def test_market_order_takes_available_liquidity():
    engine = MatchingEngine()
    engine.process_order(Order(side=Side.SELL, price=100, quantity=10))
    trades = engine.process_order(
        Order(side=Side.BUY, price=0, quantity=6, order_type=OrderType.MARKET)
    )
    assert len(trades) == 1
    assert trades[0].quantity == 6
    _, asks = engine.book.depth()
    assert asks == [(100, 4)]  # 4 units left resting on the ask side


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
