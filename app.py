import warnings
warnings.filterwarnings("ignore")

import streamlit as st
st.set_page_config(page_title="Indian Stock Research Agent", layout="wide")

import yfinance as yf
import plotly.graph_objects as go
import os
import requests
from textblob import TextBlob
from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# ── Week 5-6 imports ──────────────────────────────────────────────────────────
from week56_features import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    get_fundamentals,
    INDIAN_SECTORS, get_sector_comparison_data, plot_sector_comparison,
    get_sector_metrics_table, get_market_status,
    add_portfolio_transaction, delete_portfolio_transaction, get_portfolio_transactions,
    get_portfolio_holdings, validate_stock_symbol, validate_date_range,
)
from pdf_generator import generate_stock_report_pdf, generate_portfolio_report_pdf
from datetime import datetime, timedelta
import pandas as pd

# ── Theme Mode Selection ──────────────────────────────────────────────────────
theme_selection = st.sidebar.radio("THEME MODE", ["DARK MODE", "LIGHT MODE"], index=0, key="theme_mode_selector")
theme_mode = "light" if theme_selection == "LIGHT MODE" else "dark"
st.session_state['theme_mode'] = theme_mode

if theme_mode == "light":
    css_vars = """
    --bg-primary: #F5F7FA;         /* off-white base */
    --bg-surface: #FFFFFF;         /* card surfaces */
    --bg-elevated: #E4E7EB;        /* hover / elevated panels */
    --accent-gold: #8E704C;        /* Nifty gold styled for light mode */
    --accent-green: #008A5E;       /* positive/bullish */
    --accent-red: #D93856;         /* negative/bearish */
    --accent-blue: #0E70C0;        /* neutral info / links */
    --border-subtle: rgba(0,0,0,0.06);
    --border-strong: rgba(0,0,0,0.12);
    --text-primary: #0A0B0E;
    --text-secondary: #4A4F60;
    --text-muted: #8A8F9E;
    """
else:
    css_vars = """
    --bg-primary: #0A0B0E;         /* near-black base */
    --bg-surface: #111318;         /* card surfaces */
    --bg-elevated: #1A1D24;        /* hover / elevated panels */
    --accent-gold: #C8A96E;        /* primary accent — Nifty gold */
    --accent-green: #00C48C;       /* positive/bullish */
    --accent-red: #FF4D6A;         /* negative/bearish */
    --accent-blue: #4A9EFF;        /* neutral info / links */
    --border-subtle: rgba(255,255,255,0.06);
    --border-strong: rgba(255,255,255,0.12);
    --text-primary: #F0EDE8;
    --text-secondary: #8A8F9E;
    --text-muted: #4A4F60;
    """

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

:root {{
    {css_vars}
}}

/* Base font settings and background colors */
html, body, [class*="css"], .stMarkdown, .stText, .stButton, .stSelectbox, .stTextInput, .stMultiSelect {{
    font-family: 'DM Sans', sans-serif !important;
    color: var(--text-primary) !important;
}}

.stApp {{
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}}

/* Header typography */
h1, h2, h3, h4, h5, h6, .luxury-header {{
    font-family: 'DM Serif Display', serif !important;
    font-weight: 400 !important;
    color: var(--text-primary) !important;
    letter-spacing: 0.02em !important;
}}

/* Sidebar styling */
section[data-testid="stSidebar"] {{
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border-subtle) !important;
    box-shadow: none !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
    color: var(--text-secondary) !important;
}}

/* Metric cards override */
div[data-testid="metric-container"] {{
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 6px !important;
    padding: 16px 20px !important;
    box-shadow: none !important;
    transition: all 0.2s ease !important;
}}
div[data-testid="metric-container"]:hover {{
    background-color: var(--bg-elevated) !important;
    border-color: var(--border-strong) !important;
}}
div[data-testid="metric-container"] label {{
    color: var(--text-secondary) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    font-family: 'DM Sans', sans-serif !important;
}}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
    color: var(--text-primary) !important;
    font-size: 32px !important;
    font-weight: 500 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    margin-top: 4px !important;
}}
div[data-testid="metric-container"] div[data-testid="stMetricDelta"] {{
    font-weight: 500 !important;
    font-size: 12px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    background: transparent !important;
    padding: 0 !important;
    margin-top: 2px !important;
}}

/* Gold button styles */
.stButton > button {{
    background: transparent !important;
    color: var(--accent-gold) !important;
    border: 1px solid var(--accent-gold) !important;
    border-radius: 4px !important;
    padding: 8px 16px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
    box-shadow: none !important;
}}
.stButton > button:hover {{
    background: var(--accent-gold) !important;
    color: var(--bg-primary) !important;
    border-color: var(--accent-gold) !important;
}}
.stButton > button:active {{
    transform: translateY(1px) !important;
}}

/* Tab styling */
div[data-testid="stTabBar"] {{
    border-bottom: 1px solid var(--border-subtle) !important;
    margin-bottom: 24px !important;
    background: transparent !important;
}}
button[data-baseweb="tab"] {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    color: var(--text-secondary) !important;
    background: transparent !important;
    border: none !important;
    padding: 10px 16px !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s ease !important;
}}
button[data-baseweb="tab"]:hover {{
    color: var(--text-primary) !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--accent-gold) !important;
    border-bottom: 2px solid var(--accent-gold) !important;
    background: transparent !important;
}}

/* Inputs and selectors */
div[data-testid="stWidgetLabel"] p {{
    font-size: 12px !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    margin-bottom: 6px !important;
}}
div[data-baseweb="select"], div[data-baseweb="input"], input, textarea {{
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 4px !important;
    color: var(--text-primary) !important;
    font-family: 'IBM Plex Mono', monospace !important;
    transition: border-color 0.2s ease !important;
}}
div[data-baseweb="select"]:hover, div[data-baseweb="input"]:hover {{
    border-color: var(--border-strong) !important;
}}

/* Multi-select chips */
span[data-baseweb="tag"] {{
    background-color: var(--bg-elevated) !important;
    color: var(--accent-gold) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 4px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}}
span[data-baseweb="tag"] button {{
    color: var(--accent-gold) !important;
}}

/* Expanders as Editorial cards */
div[data-testid="stExpander"] {{
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 4px !important;
    box-shadow: none !important;
    margin-bottom: 12px !important;
}}
div[data-testid="stExpander"] details summary {{
    font-weight: 500 !important;
    color: var(--text-primary) !important;
    font-size: 14px !important;
    padding: 12px 18px !important;
}}
div[data-testid="stExpander"] details summary:hover {{
    color: var(--accent-gold) !important;
    background-color: var(--bg-elevated) !important;
}}

/* Scrollbars */
::-webkit-scrollbar {{
    width: 6px;
    height: 6px;
}}
::-webkit-scrollbar-track {{
    background: var(--bg-primary);
}}
::-webkit-scrollbar-thumb {{
    background: var(--border-strong);
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: var(--text-muted);
}}

/* Hide standard Streamlit header and footer */
div[data-testid="stHeader"] {{
    background-color: rgba(0,0,0,0) !important;
}}
footer {{
    visibility: hidden !important;
}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ORIGINAL WEEK 1-4 FUNCTIONS (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

PERIOD_MAP = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "15m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1d")
}

@st.cache_data(ttl=300)
def get_stock_data(symbol, period_label="3M", start_date=None, end_date=None):
    try:
        ticker = yf.Ticker(symbol)
        if start_date and end_date:
            hist = ticker.history(start=start_date, end=end_date)
        else:
            period, interval = PERIOD_MAP.get(period_label, ("3mo", "1d"))
            # Try with mapped interval
            hist = ticker.history(period=period, interval=interval)
            if hist is None or hist.empty:
                # Fall back to default interval
                hist = ticker.history(period=period)
        if hist is None or hist.empty:
            if start_date and end_date:
                hist = yf.download(symbol, start=start_date, end=end_date, auto_adjust=True, progress=False, ignore_tz=True)
            else:
                period, _ = PERIOD_MAP.get(period_label, ("3mo", "1d"))
                hist = yf.download(symbol, period=period, auto_adjust=True, progress=False, ignore_tz=True)
        if hist.empty:
            return None, None
        hist.columns = hist.columns.get_level_values(0)
        return hist, None
    except Exception:
        return None, None

@st.cache_data(ttl=900)
def get_sparkline_data_batch(symbols):
    """
    Fetch historical prices (7d) for multiple symbols in a single batch.
    """
    if not symbols:
        return {}
    try:
        data = yf.download(list(symbols), period="7d", interval="1d", progress=False, group_by="ticker")
        result = {}
        for sym in symbols:
            try:
                if len(symbols) == 1:
                    result[sym] = data["Close"].dropna().tolist()
                else:
                    if sym in data:
                        result[sym] = data[sym]["Close"].dropna().tolist()
                    else:
                        result[sym] = []
            except Exception:
                result[sym] = []
        return result
    except Exception:
        # Fallback to individual
        result = {}
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                hist = t.history(period="7d", interval="1d")
                if hist is not None and not hist.empty:
                    result[sym] = hist["Close"].dropna().tolist()
                else:
                    result[sym] = []
            except Exception:
                result[sym] = []
        return result

def generate_svg_sparkline(prices):
    if not prices or len(prices) < 2:
        return """<svg width="40" height="20" style="vertical-align: middle;"><line x1="0" y1="10" x2="40" y2="10" stroke="#4A4F60" stroke-width="1.5"/></svg>"""
    
    min_p, max_p = min(prices), max(prices)
    range_p = max_p - min_p if max_p != min_p else 1
    width = 40
    height = 20
    points = []
    for idx, p in enumerate(prices):
        x = (idx / (len(prices) - 1)) * width
        y = height - ((p - min_p) / range_p) * height
        points.append(f"{x:.1f},{y:.1f}")
    
    is_positive = prices[-1] >= prices[0]
    color = "#00C48C" if is_positive else "#FF4D6A"
    path_data = "M " + " L ".join(points)
    return f'<svg width="{width}" height="{height}" style="vertical-align: middle;"><path d="{path_data}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>'


@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return [], 0
    try:
        url = f"https://newsapi.org/v2/everything?q={company_name}&language=en&pageSize=5&sortBy=publishedAt&apiKey={api_key}"
        response = requests.get(url, timeout=10)
        articles = response.json().get("articles", [])
        results = []
        scores = []
        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "") or ""
            text = title + " " + description
            sentiment = TextBlob(text).sentiment.polarity
            scores.append(sentiment)
            label = "Positive" if sentiment > 0.1 else ("Negative" if sentiment < -0.1 else "Neutral")
            results.append({
                "title": title,
                "sentiment": label,
                "score": round(sentiment, 2),
                "url": article.get("url", "")
            })
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0
        return results, avg_score
    except Exception:
        return [], 0

def add_technical_indicators(hist):
    hist = hist.copy()
    hist['MA20'] = hist['Close'].rolling(window=20).mean()
    hist['MA50'] = hist['Close'].rolling(window=50).mean()
    delta = hist['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    hist['RSI'] = 100 - (100 / (1 + rs))
    return hist

def plot_stock_chart(hist, symbol, theme_mode="dark"):
    hist = add_technical_indicators(hist)
    fig = go.Figure()
    
    is_dark = (theme_mode == "dark")
    bg_surface = "#111318" if is_dark else "#FFFFFF"
    bg_primary = "#0A0B0E" if is_dark else "#F5F7FA"
    grid_color = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.05)"
    text_sec = "#8A8F9E" if is_dark else "#4A4F60"
    accent_gold = "#C8A96E" if is_dark else "#8E704C"
    border_color = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.1)"
    plotly_template = "plotly_dark" if is_dark else "plotly_white"
    
    # Bloomberg Style Candlesticks
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'],
        name=symbol,
        increasing_line_color='#00C48C',   # Bullish Emerald
        decreasing_line_color='#FF4D6A',   # Bearish Red
        increasing_fillcolor='#00C48C',
        decreasing_fillcolor='#FF4D6A'
    ))
    
    # MA20 gold line
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist['MA20'], 
        line=dict(color=accent_gold, width=1.5), # Gold
        name='MA20'
    ))
    
    # MA50 blue line
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist['MA50'], 
        line=dict(color='#4A9EFF', width=1.5), # Vibrant blue
        name='MA50'
    ))
    
    fig.update_layout(
        title=dict(
            text=f"📈 {symbol} Candlestick Analysis",
            font=dict(size=18, family="DM Serif Display", color=accent_gold)
        ),
        xaxis=dict(
            gridcolor=grid_color,
            color=text_sec,
            linecolor=border_color,
            tickfont=dict(family="IBM Plex Mono", size=11),
        ),
        yaxis=dict(
            gridcolor=grid_color,
            color=text_sec,
            linecolor=border_color,
            tickfont=dict(family="IBM Plex Mono", size=11),
        ),
        plot_bgcolor=bg_surface,
        paper_bgcolor=bg_primary,
        template=plotly_template,
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color=text_sec, family="IBM Plex Mono")
        )
    )
    return fig, hist


# ─────────────────────────────────────────────────────────────────────────────
# UI — HEADER
# ─────────────────────────────────────────────────────────────────────────────

# Initial data load if session_state is empty
if 'symbol' not in st.session_state:
    st.session_state['symbol'] = "RELIANCE.NS"
    st.session_state['period_label'] = "3M"
    hist, _ = get_stock_data("RELIANCE.NS", "3M")
    if hist is not None:
        st.session_state['hist'] = hist
        news, avg_score = get_news_sentiment("RELIANCE")
        st.session_state['news'] = news
        st.session_state['avg_score'] = avg_score

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL SIDEBAR (Bloomberg style)
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="padding: 10px 0px 15px 0px;">
    <h2 style="font-family: 'DM Serif Display'; color: var(--accent-gold); font-size: 20px; font-weight: 400; margin-bottom: 4px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px; letter-spacing: 0.05em;">TERMINAL CONTROL</h2>
</div>
""", unsafe_allow_html=True)

# Autocomplete Ticker select box
SUGGESTED_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "LTIM.NS", "ITC.NS", "WIPRO.NS", 
    "TATAMOTORS.NS", "HINDUNILVR.NS", "MARUTI.NS", "M&M.NS", 
    "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "HCLTECH.NS",
    "LT.NS", "SUNPHARMA.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
    "COALINDIA.NS", "TATASTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "ULTRACEMCO.NS", "GRASIM.NS", "TITAN.NS", "BAJFINANCE.NS",
    "BAJAJFINSV.NS", "JSWSTEEL.NS", "HINDALCO.NS", "INDUSINDBK.NS",
    "BPCL.NS", "SBILIFE.NS", "HDFCLIFE.NS", "TATACONSUM.NS",
    "APOLLOHOSP.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
    "HEROMOTOCO.NS", "EICHERMOT.NS", "NESTLEIND.NS", "BRITANNIA.NS"
]

# Get watchlist symbols to append to suggestions
wl_rows = get_watchlist()
wl_symbols = [row[0] for row in wl_rows]
all_options = list(dict.fromkeys(SUGGESTED_TICKERS + wl_symbols + ["Custom Ticker..."]))

# We can pre-select standard or last searched symbol if in session_state
default_sym_idx = 0
if 'symbol' in st.session_state and st.session_state['symbol'] in all_options:
    default_sym_idx = all_options.index(st.session_state['symbol'])

selected_option = st.sidebar.selectbox("COMMAND PALETTE", all_options, index=default_sym_idx)

if selected_option == "Custom Ticker...":
    custom_symbol = st.sidebar.text_input("ENTER CUSTOM TICKER", placeholder="e.g. SBIN.NS")
    symbol = custom_symbol.upper().strip() if custom_symbol else "RELIANCE.NS"
else:
    symbol = selected_option

# Date Selection Type selector
date_type = st.sidebar.radio("DATE SELECTION TYPE", ["Predefined Period", "Custom Date Range"], index=0, key="date_selection_type")

start_date = None
end_date = None
period_label = "3M"
valid_dates = True
date_err = ""

if date_type == "Predefined Period":
    period_label = st.sidebar.radio("PERIOD", ["1D", "1W", "1M", "3M", "1Y", "5Y"], index=3) # Default to 3M
else:
    # Use columns to put date fields side by side in the sidebar
    from datetime import datetime
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        start_date = st.date_input("START DATE", datetime.now().date() - timedelta(days=90))
    with col_d2:
        end_date = st.date_input("END DATE", datetime.now().date())
    valid_dates, date_err = validate_date_range(start_date, end_date)
    if not valid_dates:
        st.sidebar.error(date_err)

# Fetch data button styled as Gold CTA
st.sidebar.markdown('<div class="fetch-btn-container">', unsafe_allow_html=True)
fetch_clicked = st.sidebar.button("FETCH DATA", key="fetch_btn")
st.sidebar.markdown('</div>', unsafe_allow_html=True)

if fetch_clicked:
    if not valid_dates:
        st.error(f"Cannot fetch data: {date_err}")
    else:
        # Validate symbol input
        symbol_valid, symbol_err = validate_stock_symbol(symbol)
        if not symbol_valid:
            st.error(symbol_err)
        else:
            with st.spinner("Fetching stock data..."):
                hist, _ = get_stock_data(symbol, period_label, start_date=start_date, end_date=end_date)
                if hist is not None and not hist.empty:
                    st.session_state['hist'] = hist
                    st.session_state['symbol'] = symbol
                    if date_type == "Predefined Period":
                        st.session_state['period_label'] = period_label
                    else:
                        st.session_state['period_label'] = f"{start_date} to {end_date}"
                    st.session_state['start_date'] = start_date
                    st.session_state['end_date'] = end_date
                    st.session_state['date_type'] = date_type
                    
                    company_name = symbol.replace(".NS", "").replace(".BO", "")
                    news, avg_score = get_news_sentiment(company_name)
                    st.session_state['news'] = news
                    st.session_state['avg_score'] = avg_score
                    st.success(f"Loaded {symbol}")
                else:
                    market_status = get_market_status()
                    is_closed = "CLOSED" in market_status['status'] or "WEEKEND" in market_status['status']
                    
                    if is_closed and (period_label == "1D" or (start_date and start_date == end_date)):
                        st.error(f"❌ Could not retrieve intraday data for '{symbol}'. The Indian market is currently closed ({market_status['status']}). Intraday data is not available. Please choose a longer period (e.g., 1W, 1M, or 3M) or select different dates.")
                    else:
                        st.error(f"❌ Could not retrieve data for '{symbol}'. Please check if the symbol is correct and has active trading data. (For Indian stocks, verify it ends in '.NS' or '.BO', e.g. SBIN.NS).")

# Watchlist section with inline sparklines in sidebar
st.sidebar.markdown("""
<div style="margin-top: 24px; padding-bottom: 8px; border-bottom: 1px solid var(--border-subtle);">
    <h3 style="font-family: 'DM Serif Display'; color: var(--accent-gold); font-size: 16px; margin: 0; letter-spacing: 0.05em;">WATCHLIST</h3>
</div>
""", unsafe_allow_html=True)

if wl_rows:
    sparkline_batch = get_sparkline_data_batch(wl_symbols[:8])  # limit to top 8 in sidebar
    watchlist_html = ""
    for w_sym, _ in wl_rows[:8]:
        prices = sparkline_batch.get(w_sym, [])
        sparkline_svg = generate_svg_sparkline(prices)
        if len(prices) >= 2:
            pct_change = ((prices[-1] - prices[-2]) / prices[-2]) * 100
            change_str = f"{pct_change:+.1f}%"
            change_color = "var(--accent-green)" if pct_change >= 0 else "var(--accent-red)"
        else:
            change_str = "N/A"
            change_color = "var(--text-muted)"
        
        watchlist_html += f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--border-subtle);">
            <span style="font-family: 'IBM Plex Mono'; font-size: 13px; font-weight: 500; color: var(--text-primary);">{w_sym}</span>
            <span>{sparkline_svg}</span>
            <span style="font-family: 'IBM Plex Mono'; font-size: 12px; color: {change_color}; font-weight: 600;">{change_str}</span>
        </div>
        """
    st.sidebar.markdown(watchlist_html, unsafe_allow_html=True)
else:
    st.sidebar.caption("No stocks in watchlist.")

# ── Sticky Top Rail ──────────────────────────────────────────────────────────
market = get_market_status()
pulse_color = "#00C48C" if "🟢" in market['status'] or "OPEN" in market['status'] else ("#F59E0B" if "🟡" in market['status'] or "PRE-MARKET" in market['status'] else "#FF4D6A")
pulse_class = "pulse-green" if "OPEN" in market['status'] else ("pulse-amber" if "PRE-MARKET" in market['status'] else "pulse-red")
status_label = market['status'].replace("🟢", "").replace("🔴", "").replace("🟡", "").strip()

current_symbol_display = st.session_state.get('symbol', symbol)
current_period_display = st.session_state.get('period_label', period_label)

top_rail_html = f"""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; margin-bottom: 24px;">
    <div style="display: flex; align-items: center; gap: 16px;">
        <span style="font-family: 'DM Serif Display'; font-size: 1.35rem; color: var(--accent-gold); font-weight: 400; letter-spacing: 0.02em;">INDIAN STOCK PORTAL</span>
        <span style="color: var(--border-strong); font-size: 1.2rem;">|</span>
        <span style="font-family: 'IBM Plex Mono'; font-size: 11px; color: var(--text-secondary); letter-spacing: 0.05em; text-transform: uppercase;">
            MARKET DATA &nbsp;→&nbsp; <span style="color: var(--accent-gold);">{current_symbol_display}</span> &nbsp;→&nbsp; <span style="color: var(--text-primary);">{current_period_display}</span>
        </span>
    </div>
    <div style="display: flex; align-items: center; gap: 20px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span class="status-pulse-dot {pulse_class}" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: {pulse_color};"></span>
            <span style="font-family: 'IBM Plex Mono'; font-size: 11px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 0.08em; font-weight: 600;">{status_label}</span>
        </div>
        <span style="color: var(--border-strong); font-size: 1.2rem;">|</span>
        <div style="font-family: 'IBM Plex Mono'; font-size: 11px; color: var(--text-primary); letter-spacing: 0.05em;">{market['time_ist']}</div>
    </div>
</div>
"""
st.markdown(top_rail_html, unsafe_allow_html=True)

# ── Navigation Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Stock Analysis",
    "Watchlist",
    "Fundamentals",
    "Sector Comparison",
    "Portfolio Tracker",
])

# ═══════════════════════════════════════════════════════════════════════
# TAB 1: STOCK ANALYSIS (Bloomberg-tier Redesign)
# ═══════════════════════════════════════════════════════════════════════
with tab1:
    # Quick index access chips for smart empty state / quick access
    quick_indices = {
        "NIFTY 50": "^NSEI",
        "SENSEX": "^BSESN",
        "NIFTY IT": "^CNXIT",
        "NIFTY BANK": "^NSEBANK",
        "RELIANCE": "RELIANCE.NS",
        "TCS": "TCS.NS"
    }
    
    st.markdown('<p style="font-size: 10px; font-family:\'IBM Plex Mono\'; color: var(--text-muted); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:8px;">Quick Access Chips</p>', unsafe_allow_html=True)
    idx_cols = st.columns(len(quick_indices))
    for i, (name, sym_val) in enumerate(quick_indices.items()):
        if idx_cols[i].button(name, key=f"chip_{sym_val}"):
            with st.spinner(f"Loading {name}..."):
                hist, _ = get_stock_data(sym_val, period_label)
                if hist is not None:
                    st.session_state['hist'] = hist
                    st.session_state['symbol'] = sym_val
                    st.session_state['period_label'] = period_label
                    company_name = sym_val.replace(".NS", "").replace(".BO", "")
                    news, avg_score = get_news_sentiment(company_name)
                    st.session_state['news'] = news
                    st.session_state['avg_score'] = avg_score
                    st.rerun()

    if 'hist' in st.session_state:
        hist = st.session_state['hist']
        symbol = st.session_state['symbol']
        news = st.session_state.get('news', [])
        avg_score = st.session_state.get('avg_score', 0)

        current_price = float(hist['Close'].iloc[-1])
        prev_price = float(hist['Close'].iloc[-2])
        change_pct = ((current_price - prev_price) / prev_price) * 100
        sentiment_label = "Positive" if avg_score > 0.1 else ("Negative" if avg_score < -0.1 else "Neutral")

        # 1. Hero Metric Card
        change_abs = current_price - prev_price
        pct_color = "var(--accent-green)" if change_pct >= 0 else "var(--accent-red)"
        arrow = "▲" if change_pct >= 0 else "▼"
        
        hero_html = f"""
        <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 24px; margin-bottom: 20px; display: flex; align-items: baseline; justify-content: space-between;">
            <div>
                <span style="font-family: 'DM Sans'; font-size: 11px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 0.15em;">CURRENT PRICE</span>
                <div style="font-family: 'IBM Plex Mono'; font-size: 48px; font-weight: 500; color: var(--text-primary); margin-top: 4px;">
                    ₹{current_price:,.2f}
                </div>
            </div>
            <div style="text-align: right;">
                <span style="font-family: 'IBM Plex Mono'; font-size: 20px; color: {pct_color}; font-weight: 600;">
                    {arrow} {change_abs:+.2f} ({change_pct:+.2f}%)
                </span>
            </div>
        </div>
        """
        st.markdown(hero_html, unsafe_allow_html=True)

        # 2. Secondary Metrics Row with Sparklines
        open_spark = generate_svg_sparkline(hist['Open'].tolist()[-15:])
        high_spark = generate_svg_sparkline(hist['High'].tolist()[-15:])
        low_spark = generate_svg_sparkline(hist['Low'].tolist()[-15:])
        vol_spark = generate_svg_sparkline(hist['Volume'].tolist()[-15:])

        sec_cols = st.columns(4)
        with sec_cols[0]:
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">TODAY'S OPEN</span>
                    <div style="font-family: 'IBM Plex Mono'; font-size: 20px; color: var(--text-primary); margin-top: 4px;">₹{hist['Open'].iloc[-1]:,.2f}</div>
                </div>
                <div>{open_spark}</div>
            </div>
            """, unsafe_allow_html=True)
        with sec_cols[1]:
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">PERIOD HIGH</span>
                    <div style="font-family: 'IBM Plex Mono'; font-size: 20px; color: var(--text-primary); margin-top: 4px;">₹{hist['High'].max():,.2f}</div>
                </div>
                <div>{high_spark}</div>
            </div>
            """, unsafe_allow_html=True)
        with sec_cols[2]:
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">PERIOD LOW</span>
                    <div style="font-family: 'IBM Plex Mono'; font-size: 20px; color: var(--text-primary); margin-top: 4px;">₹{hist['Low'].min():,.2f}</div>
                </div>
                <div>{low_spark}</div>
            </div>
            """, unsafe_allow_html=True)
        with sec_cols[3]:
            vol_val = hist['Volume'].iloc[-1]
            if vol_val >= 10_000_000:
                vol_str = f"{vol_val/10_000_000:.2f} Cr"
            elif vol_val >= 100_000:
                vol_str = f"{vol_val/100_000:.2f} L"
            else:
                vol_str = f"{vol_val:,}"
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">VOLUME</span>
                    <div style="font-family: 'IBM Plex Mono'; font-size: 20px; color: var(--text-primary); margin-top: 4px;">{vol_str}</div>
                </div>
                <div>{vol_spark}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="margin-bottom: 24px;"></div>', unsafe_allow_html=True)

        # 3. Chart Section
        fig, hist_with_indicators = plot_stock_chart(hist, symbol, theme_mode=theme_mode)
        st.plotly_chart(fig, use_container_width=True)

        # Technical Indicators Cards Below Chart
        rsi_value = float(hist_with_indicators['RSI'].iloc[-1])
        rsi_label = "OVERBOUGHT" if rsi_value > 70 else ("OVERSOLD" if rsi_value < 30 else "NEUTRAL")
        rsi_color = "var(--accent-red)" if rsi_label == "OVERBOUGHT" else ("var(--accent-green)" if rsi_label == "OVERSOLD" else "var(--text-secondary)")
        
        st.markdown(f"""
        <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 12px 16px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-family: 'DM Sans'; font-size: 11px; color: var(--text-secondary); letter-spacing: 0.1em; text-transform: uppercase;">RSI (14-DAY) STATUS</span>
            <span style="font-family: 'IBM Plex Mono'; font-size: 13px; font-weight: 600; color: {rsi_color};">{rsi_value:.2f} — {rsi_label}</span>
        </div>
        """, unsafe_allow_html=True)

        # 4. Editorial News Section
        st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600;">LATEST PUBLICATIONS & SENTIMENT</p>', unsafe_allow_html=True)
        if news:
            news_html = ""
            for article in news:
                sent = article['sentiment']
                score = article['score']
                if sent == "Positive":
                    sent_label = "BULLISH"
                    badge_bg = "rgba(0, 196, 140, 0.1)"
                    badge_border = "rgba(0, 196, 140, 0.2)"
                    badge_color = "var(--accent-green)"
                elif sent == "Negative":
                    sent_label = "BEARISH"
                    badge_bg = "rgba(255, 77, 106, 0.1)"
                    badge_border = "rgba(255, 77, 106, 0.2)"
                    badge_color = "var(--accent-red)"
                else:
                    sent_label = "NEUTRAL"
                    badge_bg = "rgba(74, 158, 255, 0.1)"
                    badge_border = "rgba(74, 158, 255, 0.2)"
                    badge_color = "var(--accent-blue)"
                
                news_html += f"""
                <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px; margin-bottom: 12px; display: flex; gap: 16px; align-items: flex-start;">
                    <div style="width: 40px; height: 40px; background-color: var(--bg-elevated); border: 1px solid var(--border-strong); border-radius: 4px; display: flex; align-items: center; justify-content: center; font-family: 'DM Serif Display'; font-size: 18px; color: var(--accent-gold); flex-shrink: 0;">
                        N
                    </div>
                    <div style="flex-grow: 1;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-family: 'IBM Plex Mono'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.05em; text-transform: uppercase;">NEWSFEED &nbsp;•&nbsp; SCORE: {score:+.2f}</span>
                            <span style="background: {badge_bg}; border: 1px solid {badge_border}; color: {badge_color}; font-family: 'IBM Plex Mono'; font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 600; letter-spacing: 0.05em;">{sent_label}</span>
                        </div>
                        <h4 style="margin: 0 0 6px 0; font-family: 'DM Sans'; font-size: 14px; font-weight: 500; line-height: 1.4;"><a href="{article['url']}" target="_blank" style="color: var(--text-primary); text-decoration: none; transition: color 0.2s ease;">{article['title']}</a></h4>
                    </div>
                </div>
                """
            st.markdown(news_html, unsafe_allow_html=True)
        else:
            st.info("No news found or NEWS_API_KEY missing.")

        st.markdown('<div style="margin-bottom: 30px;"></div>', unsafe_allow_html=True)

        # 5. Bloomberg styled Compare Stocks Section
        st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:8px; font-weight:600;">COMPARE SECURITIES</p>', unsafe_allow_html=True)
        
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            compare_symbol = st.text_input("ENTER TICKER TO COMPARE", placeholder="e.g. TCS.NS", key="compare_input")
        with col_c2:
            st.write(""); st.write("")
            compare_clicked = st.button("RUN COMPARISON")
            
        if compare_clicked and compare_symbol:
            hist2, _ = get_stock_data(compare_symbol, period_label)
            if hist2 is not None:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=hist.index, y=hist['Close'], 
                    name=symbol, 
                    line=dict(color='#C8A96E', width=2.5) # Gold
                ))
                fig2.add_trace(go.Scatter(
                    x=hist2.index, y=hist2['Close'], 
                    name=compare_symbol, 
                    line=dict(color='#8A8F9E', width=2.0) # Slate
                ))
                fig2.update_layout(
                    title=dict(
                        text=f"📈 Price Comparison: {symbol} vs {compare_symbol}",
                        font=dict(size=16, family="DM Serif Display", color="#C8A96E")
                    ),
                    xaxis=dict(
                        gridcolor="rgba(255, 255, 255, 0.05)",
                        color="#8A8F9E",
                        linecolor="rgba(255, 255, 255, 0.1)",
                        tickfont=dict(family="IBM Plex Mono", size=11),
                    ),
                    yaxis=dict(
                        gridcolor="rgba(255, 255, 255, 0.05)",
                        color="#8A8F9E",
                        linecolor="rgba(255, 255, 255, 0.1)",
                        tickfont=dict(family="IBM Plex Mono", size=11),
                    ),
                    hovermode="x unified",
                    plot_bgcolor="#111318",
                    paper_bgcolor="#0A0B0E",
                    template="plotly_dark",
                    xaxis_rangeslider_visible=False,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1,
                        font=dict(size=11, color="#8A8F9E", family="IBM Plex Mono")
                    ),
                    margin=dict(l=40, r=40, t=60, b=40)
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.error("Could not fetch comparison stock.")

        st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:8px; font-weight:600;">EXPORT REPORTS</p>', unsafe_allow_html=True)
        
        fund_data = get_fundamentals(symbol)
        if "error" not in fund_data:
            pdf_bytes = generate_stock_report_pdf(
                symbol=symbol,
                info=fund_data,
                rsi_val=rsi_value,
                rsi_label=rsi_label,
                sentiment_label=sentiment_label,
                sentiment_score=avg_score
            )
            st.download_button(
                label="📥 DOWNLOAD PDF RESEARCH REPORT",
                data=pdf_bytes,
                file_name=f"{symbol}_research_report.pdf",
                mime="application/pdf",
                key="download_stock_pdf"
            )
        else:
            st.caption("PDF Report export unavailable (Unable to load fundamental metrics).")

        st.subheader("Ask AI About This Stock")
        user_question = st.text_input("Ask a question (e.g. Is this stock trending up?)")
        if st.button("Ask") and user_question:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                st.error("API key not found.")
            else:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-flash-latest",
                        google_api_key=api_key,
                        timeout=30, max_retries=1
                    )
                    context = f"""
Symbol: {symbol}
Current Price: ₹{current_price:.2f}
Change: {change_pct:.2f}%
High: ₹{float(hist['High'].max()):.2f}
Low: ₹{float(hist['Low'].min()):.2f}
RSI: {rsi_value:.2f} ({rsi_label})
News Sentiment: {sentiment_label} (Score: {avg_score})
"""
                    messages = [
                        SystemMessage(content="You are a financial research assistant. Always add a disclaimer that this is not investment advice."),
                        HumanMessage(content=f"Stock Data:\n{context}\n\nQuestion: {user_question}")
                    ]
                    with st.spinner("Thinking..."):
                        response = llm.invoke(messages)
                        if isinstance(response.content, list):
                            st.write(response.content[0]['text'])
                        else:
                            st.write(response.content)
                except Exception as e:
                    st.error(f"AI Error: {e}")
    else:
        st.info("👈 Select a stock and click 'Fetch Data'")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2: WATCHLIST  (Week 5-6 — new)
# ═══════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<h2 style="font-family: \'DM Serif Display\'; color: var(--accent-gold); font-size: 24px; margin-bottom: 4px;">MY WATCHLIST</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-family: \'DM Sans\'; color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Save your favourite Indian stocks here. Prices and trends are calculated in real-time.</p>', unsafe_allow_html=True)

    # 1. Quick Add Section
    col_a, col_b = st.columns([3, 1])
    with col_a:
        new_stock = st.text_input("ADD SECURITY TO WATCHLIST (e.g. SBIN.NS)", placeholder="Enter stock symbol (e.g. SBIN.NS)", key="wl_add_tab")
    with col_b:
        st.write(""); st.write("")
        add_clicked = st.button("ADD SECURITY")
        if add_clicked:
            if new_stock:
                val_ok, val_err = validate_stock_symbol(new_stock)
                if not val_ok:
                    st.error(val_err)
                else:
                    ok, msg = add_to_watchlist(new_stock)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
            else:
                st.warning("Please enter a stock symbol first.")

    st.markdown('<div style="border-bottom: 1px solid var(--border-subtle); margin: 24px 0;"></div>', unsafe_allow_html=True)

    # 2. Watchlist Grid Table
    watchlist = get_watchlist()
    if not watchlist:
        st.info("Your watchlist is empty. Add symbols using the field above.")
    else:
        # Table Headers
        cols = st.columns([1.5, 2.5, 1.5, 1.5, 1.5, 1.5, 1])
        cols[0].markdown("**Ticker**")
        cols[1].markdown("**Company Name**")
        cols[2].markdown("**Price**")
        cols[3].markdown("**Change**")
        cols[4].markdown("**Change%**")
        cols[5].markdown("**7D Trend**")
        cols[6].markdown("**Actions**")
        st.markdown('<div style="border-bottom: 1px solid var(--border-strong); margin: 4px 0 12px 0;"></div>', unsafe_allow_html=True)

        wl_symbols_tab = [item[0] for item in watchlist]
        sparkline_batch = get_sparkline_data_batch(wl_symbols_tab)

        for symbol_wl, added_on in watchlist:
            prices = sparkline_batch.get(symbol_wl, [])
            sparkline_svg = generate_svg_sparkline(prices)
            
            try:
                hist_wl, _ = get_stock_data(symbol_wl, "1M")
                if hist_wl is not None and not hist_wl.empty:
                    price = float(hist_wl['Close'].iloc[-1])
                    prev = float(hist_wl['Close'].iloc[-2])
                    chg_abs = price - prev
                    chg_pct = (chg_abs / prev) * 100
                    chg_color = "var(--accent-green)" if chg_abs >= 0 else "var(--accent-red)"
                    arrow = "▲" if chg_abs >= 0 else "▼"
                    
                    price_str = f"₹{price:,.2f}"
                    chg_str = f"{chg_abs:+.2f}"
                    pct_str = f"{arrow} {chg_pct:+.2f}%"
                else:
                    price_str, chg_str, pct_str, chg_color = "N/A", "N/A", "N/A", "var(--text-muted)"
            except Exception:
                price_str, chg_str, pct_str, chg_color = "N/A", "N/A", "N/A", "var(--text-muted)"

            cols_item = st.columns([1.5, 2.5, 1.5, 1.5, 1.5, 1.5, 1])
            if price_str == "N/A":
                cols_item[0].markdown(f"<span style='color: var(--accent-red); font-family: \"IBM Plex Mono\"; font-size:12px;'>⚠️ {symbol_wl}</span>", unsafe_allow_html=True)
                cols_item[1].markdown("<span style='color: var(--text-muted); font-size:12px;'>Data unavailable / Invalid Ticker</span>", unsafe_allow_html=True)
                cols_item[2].markdown("-")
                cols_item[3].markdown("-")
                cols_item[4].markdown("-")
                cols_item[5].markdown("-")
                if cols_item[6].button("🗑️", key=f"del_tab_{symbol_wl}"):
                    remove_from_watchlist(symbol_wl)
                    st.rerun()
            else:
                cols_item[0].markdown(f"<span style='background-color: var(--bg-elevated); border: 1px solid var(--border-subtle); padding: 2px 6px; border-radius: 4px; font-family: \"IBM Plex Mono\"; font-size: 12px; color: var(--accent-gold);'>{symbol_wl}</span>", unsafe_allow_html=True)
                cols_item[1].markdown(f"<span style='font-size: 13px; color: var(--text-primary);'>{symbol_wl.replace('.NS', '').replace('.BO', '')}</span>", unsafe_allow_html=True)
                cols_item[2].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px;'>{price_str}</span>", unsafe_allow_html=True)
                cols_item[3].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px; color: {chg_color};'>{chg_str}</span>", unsafe_allow_html=True)
                cols_item[4].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px; color: {chg_color};'>{pct_str}</span>", unsafe_allow_html=True)
                cols_item[5].markdown(sparkline_svg, unsafe_allow_html=True)
                if cols_item[6].button("🗑️", key=f"del_tab_{symbol_wl}"):
                    remove_from_watchlist(symbol_wl)
                    st.rerun()

            st.markdown('<div style="border-bottom: 1px solid var(--border-subtle); margin: 6px 0;"></div>', unsafe_allow_html=True)


def render_metric_card(label, val, trend_label=None, vs_avg=None):
    trend_html = ""
    if trend_label:
        # Match standard green for high/good and red for low/poor
        color = "var(--accent-green)" if trend_label.lower() in ["good", "high"] or "+" in trend_label else "var(--accent-red)"
        trend_html = f"<span style='color: {color}; font-size: 11px; font-family: \"IBM Plex Mono\"; font-weight:600;'>{trend_label}</span>"
    
    vs_html = ""
    if vs_avg:
        vs_html = f"<div style='font-size: 10px; color: var(--text-muted); margin-top:4px;'>vs sector avg: {vs_avg}</div>"
        
    return f"<div style='background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;'><div><span style='font-family: \"DM Sans\"; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.10em; text-transform: uppercase;'>{label}</span><div style='font-family: \"IBM Plex Mono\"; font-size: 16px; color: var(--text-primary); margin-top: 4px; font-weight: 500;'>{val}</div>{vs_html}</div><div>{trend_html}</div></div>"


# ═══════════════════════════════════════════════════════════════════════
# TAB 3: FUNDAMENTAL ANALYSIS  (Week 5-6 — new)
# ═══════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<h2 style="font-family: \'DM Serif Display\'; color: var(--accent-gold); font-size: 24px; margin-bottom: 4px;">FUNDAMENTAL ANALYSIS</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-family: \'DM Sans\'; color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Get key financial valuation, profitability, risk and performance metrics.</p>', unsafe_allow_html=True)

    col_sym, col_btn = st.columns([3, 1])
    with col_sym:
        fund_symbol = st.text_input(
            "ENTER SECURITY FOR FUNDAMENTALS",
            placeholder="RELIANCE.NS",
            key="fund_input"
        )
    with col_btn:
        st.write(""); st.write("")
        fetch_fund = st.button("RUN ANALYSIS", key="fund_btn")

    # Collapsible sidebar glossary toggle
    glossary_active = st.sidebar.toggle("📖 OPEN TERMINAL GLOSSARY", key="toggle_glossary")

    if (fetch_fund or fund_symbol) and fund_symbol:
        with st.spinner(f"Fetching fundamentals for {fund_symbol}..."):
            data = get_fundamentals(fund_symbol)

        if "error" in data:
            st.error(data["error"])
        else:
            st.markdown(f"<div style='padding: 10px 0; margin-bottom: 20px; border-bottom: 1px solid var(--border-subtle);'><h3 style='margin: 0; font-family: \"DM Serif Display\"; font-size: 20px; color: var(--accent-gold);'>{data.get('Company Name', fund_symbol)}</h3><div style='font-family: \"IBM Plex Mono\"; font-size: 11px; color: var(--text-secondary); margin-top: 4px;'>SECTOR: {data.get('Sector', 'N/A')} &nbsp;•&nbsp; INDUSTRY: {data.get('Industry', 'N/A')}</div></div>", unsafe_allow_html=True)

            # Setup layout depending on glossary toggle
            if glossary_active:
                col_left, col_right, col_gloss = st.columns([2, 2, 1.5])
            else:
                col_left, col_right = st.columns(2)

            with col_left:
                st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600;">VALUATION METRICS</p>', unsafe_allow_html=True)
                
                # Check metrics data values
                pe_ratio = data.get("P/E Ratio", "N/A")
                pe_trend = "Good" if pe_ratio != "N/A" and float(pe_ratio.replace(',', '')) < 25 else "Premium"
                
                st.markdown(render_metric_card("Market Capitalization", data.get("Market Cap", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("Current Price", data.get("Current Price", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("P/E Ratio (TTM)", pe_ratio, trend_label=pe_trend), unsafe_allow_html=True)
                st.markdown(render_metric_card("Forward P/E", data.get("Forward P/E", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("52W High", data.get("52W High", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("52W Low", data.get("52W Low", "N/A")), unsafe_allow_html=True)

            with col_right:
                st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600;">PROFITABILITY & PERFORMANCE</p>', unsafe_allow_html=True)
                
                roe_val = data.get("Return on Equity", "N/A")
                roe_trend = "High" if roe_val != "N/A" and float(roe_val.replace('%', '')) > 15 else "Low"
                
                st.markdown(render_metric_card("EPS (TTM)", data.get("EPS (TTM)", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("Return on Equity (ROE)", roe_val, trend_label=roe_trend), unsafe_allow_html=True)
                st.markdown(render_metric_card("Revenue Growth (YoY)", data.get("Revenue Growth", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("Profit Margin", data.get("Profit Margin", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("Debt/Equity Ratio", data.get("Debt/Equity", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("Beta Coefficient", data.get("Beta", "N/A")), unsafe_allow_html=True)
                st.markdown(render_metric_card("Dividend Yield", data.get("Dividend Yield", "N/A")), unsafe_allow_html=True)

            if glossary_active:
                with col_gloss:
                    st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--accent-gold); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600;">📖 GLOSSARY</p>', unsafe_allow_html=True)
                    st.markdown("""
                    <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 12px; font-family: 'DM Sans'; font-size: 12px; line-height: 1.5; color: var(--text-secondary);">
                        <strong style="color: var(--accent-gold); display:block; margin-bottom:2px;">P/E Ratio</strong>
                        Price to Earnings. High P/E suggests market expects growth. Normal range: 10-25.
                        <br/><br/>
                        <strong style="color: var(--accent-gold); display:block; margin-bottom:2px;">Return on Equity (ROE)</strong>
                        Efficiency of profits. > 15% is generally excellent.
                        <br/><br/>
                        <strong style="color: var(--accent-gold); display:block; margin-bottom:2px;">Debt/Equity</strong>
                        Financial leverage. < 1.0 is generally considered safe.
                        <br/><br/>
                        <strong style="color: var(--accent-gold); display:block; margin-bottom:2px;">Beta</strong>
                        Volatility vs market. Beta > 1 is more volatile.
                        <br/><br/>
                        <strong style="color: var(--accent-gold); display:block; margin-bottom:2px;">52W Range</strong>
                        Highest and lowest closing price over the last year.
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("---")
            st.caption("Data sourced from Yahoo Finance. P/E and EPS are trailing twelve months (TTM). Not investment advice.")

    elif fund_symbol:
        st.warning("Click RUN ANALYSIS to fetch fundamentals.")
    else:
        st.info("👈 Enter a stock symbol above and click RUN ANALYSIS.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 4: SECTOR COMPARISON  (Week 5-6 — new)
# ═══════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<h2 style="font-family: \'DM Serif Display\'; color: var(--accent-gold); font-size: 24px; margin-bottom: 4px;">SECTOR COMPARISON</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-family: \'DM Sans\'; color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Compare multiple stocks within the same industry sector side-by-side.</p>', unsafe_allow_html=True)

    # Sector select - horizontal radio styled as segmented pills
    sector_choice = st.radio(
        "CHOOSE SECTOR",
        list(INDIAN_SECTORS.keys()),
        horizontal=True,
        key="sector_select"
    )

    # Let user customise which stocks to include
    default_symbols = INDIAN_SECTORS[sector_choice]
    chosen_symbols = st.multiselect(
        "SECURITIES TO INCLUDE",
        options=default_symbols,
        default=default_symbols[:4],   # show first 4 by default
        key="sector_symbols"
    )

    # Allow adding a custom stock to the comparison
    custom_sector_stock = st.text_input(
        "ADD CUSTOM TICKER TO COMPARISON (e.g. LTIM.NS)",
        placeholder="e.g. LTIM.NS",
        key="custom_sector"
    )
    if custom_sector_stock:
        chosen_symbols = list(chosen_symbols) + [custom_sector_stock.upper().strip()]

    sector_period = st.radio("SECTOR PERIOD", ["1M", "3M", "6M", "1Y"], index=1, key="sector_period")

    if st.button("📊 RUN SECTOR ANALYSIS") and chosen_symbols:
        with st.spinner(f"Running sector analysis for {len(chosen_symbols)} securities..."):
            # Map period label
            sf_period = "3mo"
            if sector_period == "1M": sf_period = "1mo"
            elif sector_period == "6M": sf_period = "6mo"
            elif sector_period == "1Y": sf_period = "1y"
            
            df_norm = get_sector_comparison_data(chosen_symbols, period=sf_period)

        if df_norm.empty:
            st.error("Could not load data for the selected stocks.")
        else:
            fig_sector = plot_sector_comparison(df_norm, sector_choice, theme_mode=theme_mode)
            st.plotly_chart(fig_sector, use_container_width=True)

            st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600; margin-top:20px;">📋 RISK & PERFORMANCE SUMMARY</p>', unsafe_allow_html=True)
            
            # Compute advanced analytics: win rate, max drawdown, volatility
            with st.spinner("Calculating analytics..."):
                analytics_data = []
                for sym in chosen_symbols:
                    try:
                        t = yf.Ticker(sym)
                        hist_data = t.history(period=sf_period)
                        if hist_data is not None and not hist_data.empty:
                            close = hist_data["Close"]
                            daily_returns = close.pct_change().dropna()
                            
                            # Win rate
                            win_days = (daily_returns > 0).sum()
                            total_days = len(daily_returns)
                            win_rate = (win_days / total_days * 100) if total_days > 0 else 0
                            
                            # Volatility (Annualized)
                            vol = daily_returns.std() * (252 ** 0.5) * 100
                            
                            # Max Drawdown
                            cum_returns = close / close.iloc[0]
                            running_max = cum_returns.cummax()
                            drawdown = (cum_returns - running_max) / running_max
                            max_dd = drawdown.min() * 100
                            
                            analytics_data.append({
                                "Security": sym,
                                "Win Rate": f"{win_rate:.1f}%",
                                "Annual Volatility": f"{vol:.1f}%",
                                "Max Drawdown": f"{max_dd:.1f}%",
                            })
                    except Exception:
                        analytics_data.append({
                            "Security": sym,
                            "Win Rate": "N/A",
                            "Annual Volatility": "N/A",
                            "Max Drawdown": "N/A",
                        })
                
                df_analytics = pd.DataFrame(analytics_data)
                
            if not df_analytics.empty:
                st.dataframe(df_analytics, use_container_width=True, hide_index=True)
            else:
                st.info("Could not load analytics table.")

    elif not chosen_symbols:
        st.warning("Please select at least one stock.")

    st.markdown("---")
    st.caption("💡 Tip: The chart normalises all stocks to a base of 100 so you can compare % growth — not absolute prices.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 5: PORTFOLIO TRACKER  (New)
# ═══════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<h2 style="font-family: \'DM Serif Display\'; color: var(--accent-gold); font-size: 24px; margin-bottom: 4px;">PORTFOLIO TRACKER</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-family: \'DM Sans\'; color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Manage your holdings and track performance in real-time.</p>', unsafe_allow_html=True)

    # 1. Add Transaction Section
    st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:8px; font-weight:600;">ADD TRANSACTION</p>', unsafe_allow_html=True)
    
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
    with col_t1:
        tx_sym = st.text_input("SYMBOL (e.g. INFY.NS)", placeholder="INFY.NS", key="tx_sym_input")
    with col_t2:
        tx_qty = st.number_input("QUANTITY", min_value=0.01, step=1.0, value=10.0, key="tx_qty_input")
    with col_t3:
        tx_prc = st.number_input("BUY PRICE (₹)", min_value=0.01, step=1.0, value=1500.0, key="tx_prc_input")
    with col_t4:
        tx_date = st.date_input("BUY DATE", datetime.now().date(), key="tx_date_input")

    if st.button("➕ ADD TRANSACTION", key="add_tx_btn"):
        if tx_sym:
            # Validate input symbol
            tx_valid, tx_err = validate_stock_symbol(tx_sym)
            if not tx_valid:
                st.error(tx_err)
            else:
                ok, msg = add_portfolio_transaction(
                    symbol=tx_sym,
                    quantity=tx_qty,
                    buy_price=tx_prc,
                    buy_date=tx_date.strftime("%Y-%m-%d")
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.error("Please enter a stock symbol.")

    st.markdown('<div style="border-bottom: 1px solid var(--border-subtle); margin: 24px 0;"></div>', unsafe_allow_html=True)

    # 2. Portfolio Overview Metrics
    transactions = get_portfolio_transactions()
    holdings = get_portfolio_holdings()

    if not holdings:
        st.info("No active holdings in your portfolio. Add transaction details above.")
    else:
        # Fetch current prices for active holdings in a batch
        active_symbols = list(holdings.keys())
        with st.spinner("Fetching current prices for holdings..."):
            try:
                current_data = yf.download(active_symbols, period="1d", progress=False)
                prices_map = {}
                if len(active_symbols) == 1:
                    close_series = current_data["Close"].dropna()
                    prices_map[active_symbols[0]] = float(close_series.iloc[-1]) if not close_series.empty else 0.0
                else:
                    for s in active_symbols:
                        try:
                            close_series = current_data["Close"][s].dropna()
                            prices_map[s] = float(close_series.iloc[-1]) if not close_series.empty else 0.0
                        except Exception:
                            t = yf.Ticker(s)
                            prices_map[s] = float(t.history(period="1d")["Close"].iloc[-1])
            except Exception:
                prices_map = {}
                for s in active_symbols:
                    try:
                        t = yf.Ticker(s)
                        prices_map[s] = float(t.history(period="1d")["Close"].iloc[-1])
                    except Exception:
                        prices_map[s] = 0.0

        # Update holdings with real-time prices
        total_cost = 0.0
        total_value = 0.0
        
        for sym, hdata in list(holdings.items()):
            curr_prc = prices_map.get(sym, 0.0)
            if curr_prc == 0.0:
                f_data = get_fundamentals(sym)
                if "error" not in f_data:
                    curr_prc_str = f_data.get("Current Price", "₹0").replace("₹", "").replace(",", "")
                    try:
                        curr_prc = float(curr_prc_str)
                    except ValueError:
                        curr_prc = 0.0
            
            hdata["current_price"] = curr_prc
            hdata["current_value"] = hdata["quantity"] * curr_prc
            total_cost += hdata["total_cost"]
            total_value += hdata["current_value"]

        total_return_abs = total_value - total_cost
        total_return_pct = (total_return_abs / total_cost * 100) if total_cost > 0 else 0.0

        summary_stats = {
            "total_cost": total_cost,
            "total_value": total_value,
            "total_return_abs": total_return_abs,
            "total_return_pct": total_return_pct
        }

        # Render Metrics
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px;">
                <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">TOTAL INVESTED</span>
                <div style="font-family: 'IBM Plex Mono'; font-size: 24px; color: var(--text-primary); margin-top: 4px; font-weight: 500;">₹{total_cost:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col2:
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px;">
                <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">CURRENT VALUE</span>
                <div style="font-family: 'IBM Plex Mono'; font-size: 24px; color: var(--text-primary); margin-top: 4px; font-weight: 500;">₹{total_value:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col3:
            ret_color = "var(--accent-green)" if total_return_abs >= 0 else "var(--accent-red)"
            arrow = "▲" if total_return_abs >= 0 else "▼"
            st.markdown(f"""
            <div style="background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 16px;">
                <span style="font-family: 'DM Sans'; font-size: 10px; color: var(--text-secondary); letter-spacing: 0.12em; text-transform: uppercase;">PORTFOLIO RETURN</span>
                <div style="font-family: 'IBM Plex Mono'; font-size: 24px; color: {ret_color}; margin-top: 4px; font-weight: 500;">
                    {arrow} ₹{total_return_abs:,.2f} ({total_return_pct:+.2f}%)
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="margin-bottom: 24px;"></div>', unsafe_allow_html=True)

        # Download Portfolio PDF Button
        st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:8px; font-weight:600;">PORTFOLIO ACTIONS</p>', unsafe_allow_html=True)
        portfolio_pdf = generate_portfolio_report_pdf(holdings, transactions, summary_stats)
        st.download_button(
            label="📥 DOWNLOAD PORTFOLIO PDF REPORT",
            data=portfolio_pdf,
            file_name="portfolio_valuation_report.pdf",
            mime="application/pdf",
            key="download_port_pdf"
        )
        st.markdown('<div style="margin-bottom: 24px;"></div>', unsafe_allow_html=True)

        # 3. Active Holdings Table
        st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600;">ACTIVE HOLDINGS</p>', unsafe_allow_html=True)
        
        # Table Headers
        hcols = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
        hcols[0].markdown("**Ticker**")
        hcols[1].markdown("**Shares Owned**")
        hcols[2].markdown("**Avg Buy Price**")
        hcols[3].markdown("**Current Price**")
        hcols[4].markdown("**Cost Basis**")
        hcols[5].markdown("**Current Value**")
        hcols[6].markdown("**Gain / Loss**")
        st.markdown('<div style="border-bottom: 1px solid var(--border-strong); margin: 4px 0 12px 0;"></div>', unsafe_allow_html=True)

        for sym, hdata in holdings.items():
            cost = hdata["total_cost"]
            val = hdata["current_value"]
            ret_abs = val - cost
            ret_pct = (ret_abs / cost * 100) if cost > 0 else 0.0
            color = "var(--accent-green)" if ret_abs >= 0 else "var(--accent-red)"
            arrow = "▲" if ret_abs >= 0 else "▼"

            cols_item = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
            cols_item[0].markdown(f"<span style='background-color: var(--bg-elevated); border: 1px solid var(--border-subtle); padding: 2px 6px; border-radius: 4px; font-family: \"IBM Plex Mono\"; font-size: 12px; color: var(--accent-gold);'>{sym}</span>", unsafe_allow_html=True)
            cols_item[1].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px;'>{hdata['quantity']:,.2f}</span>", unsafe_allow_html=True)
            cols_item[2].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px;'>₹{hdata['avg_price']:,.2f}</span>", unsafe_allow_html=True)
            cols_item[3].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px;'>₹{hdata['current_price']:,.2f}</span>", unsafe_allow_html=True)
            cols_item[4].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px;'>₹{cost:,.2f}</span>", unsafe_allow_html=True)
            cols_item[5].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px;'>₹{val:,.2f}</span>", unsafe_allow_html=True)
            cols_item[6].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 13px; color: {color};'>{arrow} {ret_pct:+.1f}%</span>", unsafe_allow_html=True)
            st.markdown('<div style="border-bottom: 1px solid var(--border-subtle); margin: 6px 0;"></div>', unsafe_allow_html=True)

        st.markdown('<div style="margin-bottom: 24px;"></div>', unsafe_allow_html=True)

        # 4. Individual Transactions Log
        st.markdown('<p style="font-size: 11px; font-family:\'DM Sans\'; color: var(--text-secondary); letter-spacing:0.15em; text-transform:uppercase; margin-bottom:12px; font-weight:600;">TRANSACTION LOG</p>', unsafe_allow_html=True)
        
        tcols = st.columns([1.5, 2, 2, 2.5, 2.5, 1])
        tcols[0].markdown("**ID**")
        tcols[1].markdown("**Ticker**")
        tcols[2].markdown("**Buy Date**")
        tcols[3].markdown("**Quantity**")
        tcols[4].markdown("**Buy Price**")
        tcols[5].markdown("**Action**")
        st.markdown('<div style="border-bottom: 1px solid var(--border-strong); margin: 4px 0 12px 0;"></div>', unsafe_allow_html=True)

        for tid, symbol_tx, qty, price, date in transactions:
            cols_tx = st.columns([1.5, 2, 2, 2.5, 2.5, 1])
            cols_tx[0].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 12px; color: var(--text-muted);'>#{tid}</span>", unsafe_allow_html=True)
            cols_tx[1].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 12px; font-weight: 500; color: var(--text-primary);'>{symbol_tx}</span>", unsafe_allow_html=True)
            cols_tx[2].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 12px;'>{date}</span>", unsafe_allow_html=True)
            cols_tx[3].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 12px;'>{qty:,.2f}</span>", unsafe_allow_html=True)
            cols_tx[4].markdown(f"<span style='font-family: \"IBM Plex Mono\"; font-size: 12px;'>₹{price:,.2f}</span>", unsafe_allow_html=True)
            if cols_tx[5].button("🗑️", key=f"del_tx_{tid}"):
                delete_portfolio_transaction(tid)
                st.success("Deleted transaction!")
                st.rerun()
            st.markdown('<div style="border-bottom: 1px dashed var(--border-subtle); margin: 6px 0;"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("⚠️ Educational purposes only. Not financial advice. Data sourced from Yahoo Finance & NewsAPI.")
