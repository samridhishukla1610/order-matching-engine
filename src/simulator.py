"""
simulator.py
Generates random order flow to stress-test the matching engine and demonstrate
throughput. Run directly: `python -m src.simulator`
"""

import random
import time
from .order import Order, Side, OrderType
from .matching_engine import MatchingEngine


def run_simulation(num_orders: int = 5000, mid_price: float = 100.0, seed: int = 42) -> MatchingEngine:
    random.seed(seed)
    engine = MatchingEngine()

    start = time.perf_counter()
    for _ in range(num_orders):
        side = random.choice([Side.BUY, Side.SELL])
        # Prices are drawn from the SAME range around mid_price for both sides,
        # so buy and sell orders will naturally overlap and cross sometimes —
        # exactly like a real, somewhat noisy market.
        price = round(mid_price + random.uniform(-2.0, 2.0), 2)
        qty = random.randint(1, 100)
        order = Order(side=side, price=price, quantity=qty, order_type=OrderType.LIMIT)
        engine.process_order(order)
    elapsed = time.perf_counter() - start

    print(f"Processed {num_orders:,} orders in {elapsed:.4f}s "
          f"({num_orders / elapsed:,.0f} orders/sec)")
    print(f"Total trades executed: {len(engine.trades):,}")
    bids, asks = engine.book.depth(5)
    print("Top 5 bid levels:", bids)
    print("Top 5 ask levels:", asks)
    return engine


if __name__ == "__main__":
    run_simulation()
