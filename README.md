# 📈 Order Matching Engine — Paper Trading Terminal

A fully functional **limit order book matching engine** with a live paper-trading terminal built in Python + Streamlit. Start with **₹1,00,000 virtual cash** and trade 5 simulated Indian market tickers against a market-maker bot.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Why I built this

Most people treat stock trading as a black box — you click buy, something happens, shares appear. I wanted to understand what actually happens in between. Every exchange in the world runs a **limit order book**: a data structure that maintains every resting order sorted by price and time, and matches them in microseconds. This project is my implementation of that from scratch, with a paper trading UI on top so you can actually interact with it.

## Features

- **Virtual ₹1,00,000 paper trading** — real cash/position tracking, P&L, order validation
- **5 Indian tickers** — RELIANCE, TCS, INFY, HDFC, NIFTYBEES (ETF proxy) each with their own independent order book
- **Market maker bot** — continuously posts bid/ask quotes with a drifting mid price so there's always liquidity
- **Live price chart** — trade executions plotted over time per ticker
- **Open order management** — view and cancel individual resting limit orders
- **Full trade history** — every fill with price, quantity, and cash impact
- **Limit & Market orders** — limit orders rest in the book; market orders take available liquidity immediately

## Engine Design

| Concept | Implementation |
|---|---|
| Matching rule | Price-time priority (FIFO within a price level) |
| Data structure | Max-heap (bids) + min-heap (asks) via Python `heapq` |
| Price levels | `deque` per level for O(1) FIFO append/pop |
| Deletion | Lazy — stale levels cleaned on next access, not immediately |
| Trade price | Resting order's price (standard exchange convention) |
| Complexity | O(log n) per order |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/order-matching-engine.git
cd order-matching-engine

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Project Structure

```
order-matching-engine/
├── app.py                  # Streamlit UI — paper trading terminal
├── requirements.txt
├── .streamlit/
│   └── config.toml         # Dark terminal theme
└── src/
    ├── order.py            # Order, Trade, Side, OrderType dataclasses
    ├── order_book.py       # Heap-based limit order book
    ├── matching_engine.py  # Price-time priority matching + portfolio integration
    ├── portfolio.py        # Virtual cash, positions, P&L tracking
    ├── market_maker.py     # Algorithmic market maker bot
    └── simulator.py        # Stress-test / throughput benchmark
```

## Run Tests

```bash
python -m pytest tests/
```

## Stress Test

```bash
python -m src.simulator
```

Processes 5,000 random orders and prints throughput (typically 100k–300k orders/sec).

---

*Educational project — not a real exchange. All money is virtual.*
