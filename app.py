"""
app.py
Paper-trading terminal built on top of the order matching engine.

Features
--------
- Virtual ₹1,00,000 starting cash, real-time portfolio P&L
- Multiple Indian tickers (RELIANCE, TCS, INFY, HDFC, NIFTY50), each with its own order book
- Market-maker bot keeps every book liquid with a drifting mid price
- Candlestick price chart with volume panel
- Open order management — cancel individual resting orders
- Full trade history with per-trade cash impact

Run with: streamlit run app.py
"""

import time
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.order import Order, Side, OrderType
from src.matching_engine import MatchingEngine
from src.portfolio import Portfolio, STARTING_CASH
from src.market_maker import MarketMaker

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Paper Trading Terminal", layout="wide")

# ---------------------------------------------------------------------------
# CSS — exchange terminal look
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace !important; }
.stApp { background-color: #0A0E13; }

button, input, select, textarea, div[data-baseweb="select"] > div,
.stNumberInput input, .stSlider { border-radius: 0px !important; }

section[data-testid="stSidebar"] { background-color: #0D1218; border-right: 1px solid #232B33; }

div.stButton > button {
    background-color: #11161D; color: #D7DEE4; border: 1px solid #2E3640;
    text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; font-size: 0.78rem;
}
div.stButton > button:hover { border-color: #16C784; color: #16C784; }
div.stButton > button[kind="primary"] { background-color: #16C784; color: #06120C; border: 1px solid #16C784; }
div.stButton > button[kind="primary"]:hover { background-color: #13B377; }

label, .stSelectbox label, .stNumberInput label, .stSlider label {
    text-transform: uppercase !important; letter-spacing: 0.08em !important;
    font-size: 0.72rem !important; color: #5C6773 !important;
}

.eyebrow  { color:#5C6773; font-size:.75rem; letter-spacing:.16em; text-transform:uppercase; margin-bottom:4px; }
.headline { color:#D7DEE4; font-size:2rem;   font-weight:700; margin:0 0 4px 0; }
.subhead  { color:#5C6773; font-size:.9rem;  margin-bottom:22px; }

.ticker-bar {
    display:flex; align-items:center; gap:26px; flex-wrap:wrap;
    background:#0D1218; border:1px solid #232B33; padding:10px 18px;
    margin-bottom:20px; font-size:.85rem; letter-spacing:.03em;
}
.ticker-dot { width:8px; height:8px; border-radius:50%; background:#FFB020;
    display:inline-block; margin-right:6px; animation:pulse 1.6s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
.ticker-live { color:#FFB020; font-weight:700; }
.ticker-item { color:#5C6773; }
.ticker-item b { color:#D7DEE4; font-weight:600; margin-left:6px; }

/* Portfolio cards */
.pf-grid  { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
.pf-card  { background:#0D1218; border:1px solid #232B33; padding:14px 20px; min-width:140px; flex:1; }
.pf-label { color:#5C6773; font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; margin-bottom:4px; }
.pf-value { color:#D7DEE4; font-size:1.25rem; font-weight:700; }
.pf-value.green { color:#16C784; }
.pf-value.red   { color:#FF5C5C; }
.pf-value.gold  { color:#FFB020; }

.ob-panel-title { font-size:.78rem; letter-spacing:.1em; text-transform:uppercase; margin-bottom:8px; }
.ob-panel-title.bids { color:#16C784; }
.ob-panel-title.asks { color:#FF5C5C; }

.ob-table, .trade-table { width:100%; border-collapse:collapse; font-size:.85rem; }
.ob-table th, .trade-table th {
    text-align:left; color:#5C6773; text-transform:uppercase; font-size:.68rem;
    letter-spacing:.07em; padding:6px 10px; border-bottom:1px solid #232B33;
}
.ob-table td, .trade-table td {
    padding:5px 10px; border-bottom:1px solid #161B21;
    font-variant-numeric:tabular-nums; color:#D7DEE4;
}
.ob-table.bids td.price { color:#16C784; font-weight:600; }
.ob-table.asks td.price { color:#FF5C5C; font-weight:600; }
.ob-table td.qty, .trade-table td.num { text-align:right; }

.empty-state { border:1px dashed #232B33; padding:18px; color:#5C6773; font-size:.85rem; text-align:center; }
.warn  { color:#FFB020; font-size:.82rem; padding:8px 12px; border:1px solid #332800; background:#1A1400; }
.badge-buy  { color:#16C784; font-weight:700; }
.badge-sell { color:#FF5C5C; font-weight:700; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tickers & session state bootstrap
# ---------------------------------------------------------------------------
TICKERS = {
    "RELIANCE":  {"mid": 2950.0, "spread": 2.50, "drift": 5.0},
    "TCS":       {"mid": 3820.0, "spread": 3.00, "drift": 6.0},
    "INFY":      {"mid": 1480.0, "spread": 1.50, "drift": 3.0},
    "HDFC":      {"mid": 1650.0, "spread": 1.50, "drift": 3.5},
    "NIFTYBEES": {"mid": 245.0,  "spread": 0.10, "drift": 0.20},  # ETF proxy for NIFTY50
}

def _init_state():
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = Portfolio()
    if "engines" not in st.session_state:
        st.session_state.engines = {t: MatchingEngine() for t in TICKERS}
    if "makers" not in st.session_state:
        st.session_state.makers = {
            t: MarketMaker(
                mid_price=cfg["mid"],
                spread_step=cfg["spread"],
                drift_sigma=cfg["drift"],
            )
            for t, cfg in TICKERS.items()
        }
    if "price_history" not in st.session_state:
        # ticker -> list of (timestamp, price) for charting
        st.session_state.price_history = {t: [] for t in TICKERS}
    if "mm_enabled" not in st.session_state:
        st.session_state.mm_enabled = True
    if "active_ticker" not in st.session_state:
        st.session_state.active_ticker = "RELIANCE"
    if "mm_ticks" not in st.session_state:
        # seed each book with initial liquidity
        for t in TICKERS:
            for _ in range(6):
                st.session_state.makers[t].tick(st.session_state.engines[t])

_init_state()

portfolio   = st.session_state.portfolio
engines     = st.session_state.engines
makers      = st.session_state.makers
price_hist  = st.session_state.price_history

# ---------------------------------------------------------------------------
# Market-maker tick helper
# ---------------------------------------------------------------------------
def mm_tick_all():
    """Advance market maker one step on all tickers, record last trade price."""
    for t in TICKERS:
        eng = engines[t]
        prev_count = len(eng.trades)
        makers[t].tick(eng)
        new_trades = eng.trades[prev_count:]
        if new_trades:
            price_hist[t].append((time.time(), new_trades[-1].price))
            # Keep history bounded
            if len(price_hist[t]) > 500:
                price_hist[t] = price_hist[t][-500:]

def mm_tick_active():
    """Advance market maker on the active ticker only."""
    t = st.session_state.active_ticker
    eng = engines[t]
    prev_count = len(eng.trades)
    makers[t].tick(eng)
    new_trades = eng.trades[prev_count:]
    if new_trades:
        price_hist[t].append((time.time(), new_trades[-1].price))
        if len(price_hist[t]) > 500:
            price_hist[t] = price_hist[t][-500:]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="eyebrow">Paper Trading Terminal // Price-Time Priority Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="headline">Order Matching Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="subhead">Virtual ₹1,00,000 starting cash — trade, manage positions, cancel orders. No real money.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Portfolio summary cards
# ---------------------------------------------------------------------------
last_prices = {t: (price_hist[t][-1][1] if price_hist[t] else makers[t].current_mid()) for t in TICKERS}
equity   = portfolio.total_equity(last_prices)
pnl      = equity - STARTING_CASH
pnl_pct  = (pnl / STARTING_CASH) * 100
pnl_cls  = "green" if pnl >= 0 else "red"
pnl_sign = "+" if pnl >= 0 else ""

active_pos = {t: q for t, q in portfolio.positions.items() if q != 0}
pos_str = ", ".join(f"{t}: {q:+d}" for t, q in active_pos.items()) if active_pos else "Flat"

st.markdown(f"""
<div class="pf-grid">
  <div class="pf-card"><div class="pf-label">Cash</div><div class="pf-value gold">₹{portfolio.cash:,.2f}</div></div>
  <div class="pf-card"><div class="pf-label">Available Cash</div><div class="pf-value gold">₹{portfolio.available_cash():,.2f}</div></div>
  <div class="pf-card"><div class="pf-label">Total Equity</div><div class="pf-value">₹{equity:,.2f}</div></div>
  <div class="pf-card"><div class="pf-label">P&amp;L</div><div class="pf-value {pnl_cls}">{pnl_sign}₹{pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)</div></div>
  <div class="pf-card"><div class="pf-label">Positions</div><div class="pf-value" style="font-size:.9rem">{pos_str}</div></div>
  <div class="pf-card"><div class="pf-label">Trades</div><div class="pf-value">{len(portfolio.trade_history)}</div></div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Ticker selector + ticker bar
# ---------------------------------------------------------------------------
_ticker_keys = list(TICKERS.keys())
_saved = st.session_state.active_ticker
_default_index = _ticker_keys.index(_saved) if _saved in _ticker_keys else 0

ticker = st.selectbox(
    "Active Ticker",
    _ticker_keys,
    index=_default_index,
    key="ticker_select",
)
st.session_state.active_ticker = ticker

engine = engines[ticker]
maker  = makers[ticker]

best_bid = engine.book.best_price(Side.BUY)
best_ask = engine.book.best_price(Side.SELL)
spread_val = f"{(best_ask - best_bid):.2f}" if (best_bid and best_ask) else "—"
last_px    = last_prices[ticker]

ticker_label = f"{ticker} (ETF proxy)" if ticker == "NIFTYBEES" else ticker
st.markdown(f"""
<div class="ticker-bar">
    <span class="ticker-dot"></span><span class="ticker-live">{ticker_label}</span>
    <span class="ticker-item">LAST<b>₹{last_px:,.2f}</b></span>
    <span class="ticker-item">BID<b>{f"₹{best_bid:,.2f}" if best_bid else "—"}</b></span>
    <span class="ticker-item">ASK<b>{f"₹{best_ask:,.2f}" if best_ask else "—"}</b></span>
    <span class="ticker-item">SPREAD<b>{spread_val}</b></span>
    <span class="ticker-item">YOUR POS<b>{portfolio.positions.get(ticker, 0):+d} shares</b></span>
    <span class="ticker-item">BOOK TRADES<b>{len(engine.trades):,}</b></span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
col_entry, col_book, col_chart = st.columns([1, 1, 2])

# ── LEFT: Order entry ──────────────────────────────────────────────────────
with col_entry:
    st.markdown('<div class="ob-panel-title">Submit Order</div>', unsafe_allow_html=True)

    side_str   = st.selectbox("Side", ["BUY", "SELL"])
    order_type = st.selectbox("Order Type", ["LIMIT", "MARKET"])

    ref_price = best_ask if side_str == "BUY" else best_bid
    default_px = float(ref_price) if ref_price else float(maker.current_mid())
    price_input = st.number_input(
        "Price", value=default_px, step=0.5 if ticker not in ("BTC",) else 50.0,
        disabled=(order_type == "MARKET"),
        format="%.2f",
    )
    qty_input = st.number_input("Quantity (shares)", value=10, step=1, min_value=1)

    # Validation — Fix 3 & 4: covers all order types and sides
    side_enum = Side[side_str]
    warning_msg = None
    qty_to_submit = int(qty_input)

    if side_enum == Side.BUY:
        if order_type == "LIMIT":
            cost = price_input * qty_to_submit
            if not portfolio.can_afford(price_input, qty_to_submit):
                warning_msg = f"Insufficient cash. Need ₹{cost:,.2f}, available ₹{portfolio.available_cash():,.2f} (₹{portfolio.reserved_cash():,.2f} reserved in open orders)."
        else:  # MARKET BUY — Fix 3: cap to max affordable at best ask
            if best_ask:
                max_affordable = int(portfolio.available_cash() // best_ask)
                if max_affordable == 0:
                    warning_msg = f"Insufficient cash. Best ask ₹{best_ask:,.2f}, available ₹{portfolio.available_cash():,.2f}."
                elif qty_to_submit > max_affordable:
                    qty_to_submit = max_affordable
                    st.info(f"Quantity capped to {max_affordable} shares (max affordable at best ask ₹{best_ask:,.2f}).")
            else:
                warning_msg = "No liquidity — cannot place market buy."

    else:  # SELL — Fix 4: guard applies to BOTH limit and market sells
        held = portfolio.positions.get(ticker, 0)
        if held < qty_to_submit:
            warning_msg = f"You only hold {held} shares of {ticker}. Cannot sell {qty_to_submit}."

    if warning_msg:
        st.markdown(f'<div class="warn">⚠ {warning_msg}</div>', unsafe_allow_html=True)

    submit_disabled = warning_msg is not None
    if st.button("Submit Order", type="primary", disabled=submit_disabled):
        # Hard guard — re-validate inside the handler so a Streamlit rerun
        # race can never execute an order that failed validation
        if warning_msg is not None:
            st.error("Order blocked by validation. Please review the warning above.")
            st.stop()
        if qty_to_submit <= 0:
            st.error("Quantity must be at least 1.")
            st.stop()

        order = Order(
            side=side_enum,
            price=round(price_input, 2) if order_type == "LIMIT" else 0,
            quantity=qty_to_submit,
            order_type=OrderType[order_type],
        )
        try:
            trades = engine.process_order(
                order,
                portfolio=portfolio,
                ticker=ticker,
                is_player_order=True,
            )
        except ValueError as e:
            # Fix 1 — wash trade rejection surfaces here
            st.error(str(e))
            trades = []

        if trades:
            price_hist[ticker].append((time.time(), trades[-1].price))
            filled_qty = sum(t.quantity for t in trades)
            st.success(f"{len(trades)} trade(s) — {filled_qty} units @ ₹{trades[-1].price:,.2f}")
        elif not trades and not warning_msg:
            msg = "Order resting in book." if order_type == "LIMIT" else "No liquidity to fill."
            st.info(msg)

    # Market maker tick button
    st.divider()
    st.markdown('<div class="ob-panel-title">Market Controls</div>', unsafe_allow_html=True)

    mm_on = st.toggle("Market Maker Bot", value=st.session_state.mm_enabled)
    st.session_state.mm_enabled = mm_on

    if st.button("⏩ Advance Market (1 tick)"):
        mm_tick_active()
        st.rerun()

    if st.button("⏩⏩ Advance Market (10 ticks)"):
        for _ in range(10):
            mm_tick_active()
        st.rerun()

    st.divider()
    if st.button("🔄 Reset Everything"):
        for key in ["portfolio", "engines", "makers", "price_history", "mm_ticks"]:
            st.session_state.pop(key, None)
        st.rerun()

# ── MIDDLE: Order book depth ───────────────────────────────────────────────
def render_depth_table(rows, label, css_class):
    if not rows:
        return (f'<div class="ob-panel-title {css_class}">{label}</div>'
                f'<div class="empty-state">No {label.lower()} resting</div>')
    body = "".join(
        f'<tr><td class="price">₹{p:,.2f}</td><td class="qty">{q:,}</td></tr>'
        for p, q in rows
    )
    return f"""
    <div class="ob-panel-title {css_class}">{label}</div>
    <table class="ob-table {css_class}">
        <tr><th>Price (₹)</th><th style="text-align:right">Qty</th></tr>
        {body}
    </table>"""

with col_book:
    bids, asks = engine.book.depth(8)
    st.markdown(render_depth_table(bids, "Bids", "bids"), unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(render_depth_table(asks, "Asks", "asks"), unsafe_allow_html=True)

# ── RIGHT: Price chart ─────────────────────────────────────────────────────
with col_chart:
    st.markdown(f'<div class="ob-panel-title">Price Chart — {ticker}</div>', unsafe_allow_html=True)
    hist = price_hist[ticker]

    if len(hist) >= 4:
        df = pd.DataFrame(hist, columns=["ts", "price"])
        df["time"] = pd.to_datetime(df["ts"], unit="s")

        # Build OHLC candles — group every 5 trades into one candle
        df["candle"] = df.index // 5
        ohlc = df.groupby("candle").agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            time=("time", "last"),
            volume=("price", "count"),
        ).reset_index(drop=True)

        colors = ["#16C784" if c >= o else "#FF5C5C"
                  for c, o in zip(ohlc["close"], ohlc["open"])]

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.75, 0.25],
            vertical_spacing=0.03,
        )

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=ohlc["time"],
            open=ohlc["open"],
            high=ohlc["high"],
            low=ohlc["low"],
            close=ohlc["close"],
            increasing_line_color="#16C784",
            increasing_fillcolor="#16C784",
            decreasing_line_color="#FF5C5C",
            decreasing_fillcolor="#FF5C5C",
            line_width=1,
            whiskerwidth=0.5,
            name="Price",
            showlegend=False,
        ), row=1, col=1)

        # Last price horizontal line
        last_close = float(ohlc["close"].iloc[-1])
        fig.add_hline(
            y=last_close,
            line_dash="dot",
            line_color="#FFB020",
            line_width=1,
            row=1, col=1,
        )

        # Volume bars
        fig.add_trace(go.Bar(
            x=ohlc["time"],
            y=ohlc["volume"],
            marker_color=colors,
            marker_opacity=0.6,
            name="Volume",
            showlegend=False,
        ), row=2, col=1)

        fig.update_layout(
            plot_bgcolor="#0A0E13",
            paper_bgcolor="#0A0E13",
            margin=dict(l=0, r=0, t=4, b=0),
            height=300,
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                rangeslider=dict(visible=False),
            ),
            xaxis2=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="#5C6773", size=10, family="JetBrains Mono"),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#161B21",
                gridwidth=1,
                zeroline=False,
                tickfont=dict(color="#5C6773", size=10, family="JetBrains Mono"),
                tickprefix="₹",
                side="right",
            ),
            yaxis2=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="#5C6773", size=9, family="JetBrains Mono"),
            ),
            hoverlabel=dict(
                bgcolor="#0D1218",
                bordercolor="#232B33",
                font=dict(color="#D7DEE4", size=12, family="JetBrains Mono"),
            ),
            hovermode="x unified",
        )

        # Price annotation on the right axis
        fig.add_annotation(
            x=ohlc["time"].iloc[-1],
            y=last_close,
            xref="x", yref="y",
            text=f" ₹{last_close:,.2f}",
            showarrow=False,
            font=dict(color="#FFB020", size=11, family="JetBrains Mono"),
            xanchor="left",
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Mini stats row below chart
        if len(ohlc) >= 2:
            prev_close = float(ohlc["close"].iloc[-2])
            chg = last_close - prev_close
            chg_pct = (chg / prev_close) * 100
            chg_color = "#16C784" if chg >= 0 else "#FF5C5C"
            chg_sign = "+" if chg >= 0 else ""
            day_high = float(ohlc["high"].max())
            day_low  = float(ohlc["low"].min())
            st.markdown(f"""
            <div style="display:flex;gap:24px;font-size:.78rem;color:#5C6773;padding:4px 2px;">
                <span>LAST <b style="color:#D7DEE4">₹{last_close:,.2f}</b></span>
                <span>CHG <b style="color:{chg_color}">{chg_sign}₹{chg:,.2f} ({chg_sign}{chg_pct:.2f}%)</b></span>
                <span>HIGH <b style="color:#16C784">₹{day_high:,.2f}</b></span>
                <span>LOW <b style="color:#FF5C5C">₹{day_low:,.2f}</b></span>
                <span>CANDLES <b style="color:#D7DEE4">{len(ohlc)}</b></span>
            </div>
            """, unsafe_allow_html=True)

    elif len(hist) >= 2:
        # Fallback plain line if not enough data for candles yet
        df = pd.DataFrame(hist, columns=["ts", "price"])
        df["time"] = pd.to_datetime(df["ts"], unit="s")
        fig = go.Figure(go.Scatter(
            x=df["time"], y=df["price"],
            mode="lines",
            line=dict(color="#16C784", width=2),
            fill="tozeroy",
            fillcolor="rgba(22,199,132,0.07)",
        ))
        fig.update_layout(
            plot_bgcolor="#0A0E13", paper_bgcolor="#0A0E13",
            margin=dict(l=0, r=0, t=4, b=0), height=260,
            xaxis=dict(showgrid=False, zeroline=False,
                       tickfont=dict(color="#5C6773", size=10)),
            yaxis=dict(showgrid=True, gridcolor="#161B21",
                       tickfont=dict(color="#5C6773", size=10),
                       tickprefix="₹", side="right"),
            hoverlabel=dict(bgcolor="#0D1218", bordercolor="#232B33",
                            font=dict(color="#D7DEE4", size=12)),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown('<div class="empty-state">Advance the market a few ticks to populate the chart.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Open orders + cancel
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown('<div class="ob-panel-title">Open Orders</div>', unsafe_allow_html=True)

open_orders = [
    (oid, order, t)
    for oid, (order, t) in portfolio.open_orders.items()
    if not order.is_filled() and not order.cancelled
]

if not open_orders:
    st.markdown('<div class="empty-state">No resting orders.</div>', unsafe_allow_html=True)
else:
    hdr_cols = st.columns([1, 1, 1, 1, 1, 1])
    for col, label in zip(hdr_cols, ["Order ID", "Ticker", "Side", "Price", "Remaining", "Action"]):
        col.markdown(f"<span style='color:#5C6773;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em'>{label}</span>", unsafe_allow_html=True)

    for oid, order, t in open_orders:
        r = st.columns([1, 1, 1, 1, 1, 1])
        side_cls = "badge-buy" if order.side == Side.BUY else "badge-sell"
        r[0].markdown(f"`{oid}`")
        r[1].markdown(f"**{t}**")
        r[2].markdown(f'<span class="{side_cls}">{order.side.value}</span>', unsafe_allow_html=True)
        r[3].markdown(f"`{order.price:,.2f}`")
        r[4].markdown(f"`{order.remaining}`")
        if r[5].button("Cancel", key=f"cancel_{oid}"):
            engine_for = engines[t]
            engine_for.book.cancel(oid)
            portfolio.remove_open_order(oid)
            st.rerun()

# ---------------------------------------------------------------------------
# Trade history
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(f'<div class="ob-panel-title">Your Trade History ({len(portfolio.trade_history)} fills)</div>', unsafe_allow_html=True)

if not portfolio.trade_history:
    st.markdown('<div class="empty-state">No fills yet — submit a crossing order or advance the market.</div>', unsafe_allow_html=True)
else:
    rows = []
    for pt in reversed(portfolio.trade_history[-50:]):
        cash_cls = "badge-sell" if pt.cash_impact > 0 else "badge-buy"
        sign = "+" if pt.cash_impact > 0 else ""
        rows.append({
            "Trade": pt.trade_id,
            "Ticker": pt.ticker,
            "Side": pt.side,
            "Price": f"₹{pt.price:,.2f}",
            "Qty": pt.quantity,
            "Cash Impact": f"{sign}₹{pt.cash_impact:,.2f}",
        })
    df_hist = pd.DataFrame(rows)
    st.dataframe(df_hist, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Auto-advance market maker if enabled (on every rerun)
# ---------------------------------------------------------------------------
if st.session_state.mm_enabled:
    mm_tick_active()

# ---------------------------------------------------------------------------
# How it works
# ---------------------------------------------------------------------------
with st.expander("How this works"):
    st.markdown("""
**Paper Trading**
- You start with **₹1,00,000 virtual cash**. All money is fake — nothing real is at stake.
- Buy orders debit your cash; sell orders credit it. You can't spend more than you have or sell shares you don't own.
- Total equity = cash + mark-to-market value of all open positions.

**Market Maker Bot**
- A synthetic market maker continuously posts bid/ask quotes around a drifting mid price, so there's always liquidity to trade against.
- Use the *Advance Market* buttons to tick the market forward — each tick posts new quotes and moves the price slightly.
- Toggle the bot off to freeze the book and place orders manually.

**Order Types**
- **Limit**: rests in the book at your price until filled or cancelled.
- **Market**: takes the best available price immediately; any unfilled quantity is dropped.

**Matching Engine**
- Price-time priority: best price fills first; within a price level, earliest order fills first (FIFO).
- Data structures: max-heap (bids) + min-heap (asks) with per-level deques. O(log n) matching.
- Lazy deletion: empty price levels are cleaned up the next time they'd be touched, not immediately.
    """)
