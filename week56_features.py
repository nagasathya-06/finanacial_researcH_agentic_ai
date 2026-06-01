"""
Week 5-6: Domain Specialization — Indian Stock Analysis Assistant
New features added on top of Week 3-4 foundation:
  1. Watchlist — save/remove stocks using SQLite database
  2. Fundamental Analysis — P/E ratio, debt-to-equity, EPS, market cap
  3. Sector Comparison — compare multiple stocks in a sector side by side
  4. Indian Market Hours — notify user if market is open or closed (IST)
"""

import sqlite3
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import pytz
from datetime import datetime

# ─────────────────────────────────────────────
# 1. DATABASE SETUP (SQLite Watchlist)
# ─────────────────────────────────────────────

DB_PATH = "watchlist.db"

def init_db():
    """Create the watchlist table if it doesn't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            added_on TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_to_watchlist(symbol: str):
    """Add a stock symbol to the watchlist. Ignores duplicates."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO watchlist (symbol, added_on) VALUES (?, ?)",
            (symbol.upper(), datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        return True, f"✅ {symbol.upper()} added to watchlist!"
    except sqlite3.IntegrityError:
        return False, f"⚠️ {symbol.upper()} is already in your watchlist."
    finally:
        conn.close()

def remove_from_watchlist(symbol: str):
    """Remove a stock symbol from the watchlist."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.upper(),))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted:
        return True, f"🗑️ {symbol.upper()} removed from watchlist."
    return False, f"⚠️ {symbol.upper()} was not in your watchlist."

def get_watchlist() -> list:
    """Return all symbols currently saved in the watchlist."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, added_on FROM watchlist ORDER BY added_on DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows  # list of (symbol, added_on) tuples


# ─────────────────────────────────────────────
# 2. FUNDAMENTAL ANALYSIS
# ─────────────────────────────────────────────

def get_fundamentals(symbol: str) -> dict:
    """
    Fetch fundamental data for a stock using yfinance.
    Returns a dict with key metrics or an error message.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # yfinance sometimes returns empty dict for Indian stocks — handle gracefully
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            return {"error": "Could not fetch fundamental data. Try again or check the symbol."}

        def fmt(value, prefix="", suffix="", decimals=2):
            """Helper: format a number nicely, return N/A if missing."""
            if value is None or value == "N/A":
                return "N/A"
            try:
                if isinstance(value, (int, float)):
                    if value >= 1_00_00_00_000:   # ≥ 1000 Cr → show in Cr
                        return f"{prefix}{value/1_00_00_00_000:.2f} Lakh Cr"
                    elif value >= 1_00_00_000:     # ≥ 1 Cr
                        return f"{prefix}{value/1_00_00_000:.2f} Cr"
                    return f"{prefix}{value:.{decimals}f}{suffix}"
                return str(value)
            except Exception:
                return "N/A"

        return {
            "Company Name":     info.get("longName", symbol),
            "Sector":           info.get("sector", "N/A"),
            "Industry":         info.get("industry", "N/A"),
            "Market Cap":       fmt(info.get("marketCap"), prefix="₹"),
            "Current Price":    fmt(info.get("currentPrice") or info.get("regularMarketPrice"), prefix="₹"),
            "P/E Ratio":        fmt(info.get("trailingPE"), decimals=2),
            "Forward P/E":      fmt(info.get("forwardPE"), decimals=2),
            "EPS (TTM)":        fmt(info.get("trailingEps"), prefix="₹"),
            "Dividend Yield":   fmt(info.get("dividendYield", 0) * 100 if info.get("dividendYield") else None, suffix="%"),
            "52W High":         fmt(info.get("fiftyTwoWeekHigh"), prefix="₹"),
            "52W Low":          fmt(info.get("fiftyTwoWeekLow"), prefix="₹"),
            "Debt/Equity":      fmt(info.get("debtToEquity"), decimals=2),
            "Return on Equity": fmt(info.get("returnOnEquity", 0) * 100 if info.get("returnOnEquity") else None, suffix="%"),
            "Revenue Growth":   fmt(info.get("revenueGrowth", 0) * 100 if info.get("revenueGrowth") else None, suffix="%"),
            "Profit Margin":    fmt(info.get("profitMargins", 0) * 100 if info.get("profitMargins") else None, suffix="%"),
            "Beta":             fmt(info.get("beta"), decimals=2),
        }

    except Exception as e:
        return {"error": f"Error fetching data: {str(e)}"}


# ─────────────────────────────────────────────
# 3. SECTOR COMPARISON
# ─────────────────────────────────────────────

# Predefined Indian sector buckets for quick selection
INDIAN_SECTORS = {
    "🖥️ IT / Technology": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "🏦 Banking & Finance": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "⚡ Energy & Oil": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS"],
    "💊 Pharma & Healthcare": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"],
    "🏭 Manufacturing / FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS"],
    "🚗 Auto": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"],
}

def get_sector_comparison_data(symbols: list, period: str = "3mo") -> pd.DataFrame:
    """
    Download closing prices for multiple symbols and return a combined DataFrame.
    Normalises prices to 100 at start so all stocks are on the same scale.
    """
    frames = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period=period)
            if hist is not None and not hist.empty:
                frames[sym] = hist["Close"]
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    df.dropna(how="all", inplace=True)

    # Normalise: start value = 100, so we compare % growth
    df_normalised = (df / df.iloc[0]) * 100
    return df_normalised

def plot_sector_comparison(df_normalised: pd.DataFrame, sector_name: str) -> go.Figure:
    """Plot normalised price comparison for all stocks in the sector."""
    fig = go.Figure()
    for col in df_normalised.columns:
        fig.add_trace(go.Scatter(
            x=df_normalised.index,
            y=df_normalised[col],
            name=col,
            mode="lines"
        ))
    fig.update_layout(
        title=f"Sector Comparison: {sector_name} (Normalised to 100)",
        xaxis_title="Date",
        yaxis_title="Relative Performance (Base = 100)",
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
    )
    return fig

def get_sector_metrics_table(symbols: list) -> pd.DataFrame:
    """
    Build a quick comparison table: symbol, current price, P/E, 52W change%.
    """
    rows = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.info
            hist = t.history(period="1y")
            if hist is None or hist.empty:
                continue
            current = hist["Close"].iloc[-1]
            year_ago = hist["Close"].iloc[0]
            change_1y = ((current - year_ago) / year_ago) * 100
            rows.append({
                "Symbol": sym,
                "Price (₹)": round(current, 2),
                "1Y Change (%)": round(change_1y, 2),
                "P/E Ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
                "Sector": info.get("sector", "N/A"),
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# 4. INDIAN MARKET HOURS CHECKER
# ─────────────────────────────────────────────

def get_market_status() -> dict:
    """
    Returns whether NSE/BSE is currently open.
    Market hours: Monday–Friday, 9:15 AM – 3:30 PM IST
    """
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)

    weekday = now_ist.weekday()  # 0=Mon … 6=Sun
    hour = now_ist.hour
    minute = now_ist.minute
    time_now = hour * 60 + minute  # minutes since midnight

    market_open  = 9 * 60 + 15   # 9:15 AM
    market_close = 15 * 60 + 30  # 3:30 PM

    is_weekday = weekday < 5
    is_in_hours = market_open <= time_now <= market_close

    if is_weekday and is_in_hours:
        status = "🟢 OPEN"
        message = f"NSE/BSE is currently **open**. Last price updates are live."
    elif is_weekday and time_now < market_open:
        status = "🟡 PRE-MARKET"
        opens_in = market_open - time_now
        message = f"Market opens in {opens_in // 60}h {opens_in % 60}m (at 9:15 AM IST)."
    elif is_weekday and time_now > market_close:
        status = "🔴 CLOSED"
        message = "Market closed for today. Showing last available prices."
    else:
        status = "🔴 WEEKEND"
        days_to_monday = (7 - weekday) % 7 or 7
        message = f"Market is closed (weekend). Opens Monday at 9:15 AM IST."

    return {
        "status": status,
        "message": message,
        "time_ist": now_ist.strftime("%I:%M %p IST, %A %d %b %Y"),
    }
