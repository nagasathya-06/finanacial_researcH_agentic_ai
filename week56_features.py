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
    "IT & Technology": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Banking & Finance": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "Energy & Utilities": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS"],
    "Pharma & Healthcare": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"],
    "Consumer Goods & FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS"],
    "Automotive": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"],
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

def plot_sector_comparison(df_normalised: pd.DataFrame, sector_name: str, theme_mode: str = "dark") -> go.Figure:
    """Plot normalised price comparison for all stocks in the sector."""
    fig = go.Figure()
    # Curated modern metallic palette (gold, blue, green, red, slate, bronze tones)
    colors = ["#C8A96E", "#4A9EFF", "#00C48C", "#FF4D6A", "#8A8F9E", "#AA771C"]
    for i, col in enumerate(df_normalised.columns):
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=df_normalised.index,
            y=df_normalised[col],
            name=col,
            mode="lines",
            line=dict(width=2.5, color=color),
            hovertemplate="<b>%{text}</b>: %{y:.2f}%<extra></extra>",
            text=[col] * len(df_normalised)
        ))
        
    is_dark = (theme_mode == "dark")
    bg_surface = "#111318" if is_dark else "#FFFFFF"
    bg_primary = "#0A0B0E" if is_dark else "#F5F7FA"
    grid_color = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.05)"
    text_sec = "#8A8F9E" if is_dark else "#4A4F60"
    accent_gold = "#C8A96E" if is_dark else "#8E704C"
    border_color = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.1)"
    plotly_template = "plotly_dark" if is_dark else "plotly_white"
    
    fig.update_layout(
        title=dict(
            text=f"🏭 Sector Comparison: {sector_name} (Base = 100)",
            font=dict(size=16, family="DM Serif Display", color=accent_gold)
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
        hovermode="x unified",
        plot_bgcolor=bg_surface,
        paper_bgcolor=bg_primary,
        template=plotly_template,
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color=text_sec, family="IBM Plex Mono")
        ),
        margin=dict(l=40, r=40, t=60, b=40),
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
        status = "OPEN"
        message = "NSE/BSE is currently open. Live prices are updating."
    elif is_weekday and time_now < market_open:
        status = "PRE-MARKET"
        opens_in = market_open - time_now
        message = f"Market opens in {opens_in // 60}h {opens_in % 60}m (at 9:15 AM IST)."
    elif is_weekday and time_now > market_close:
        status = "CLOSED"
        message = "Market closed for today. Showing last available closing prices."
    else:
        status = "WEEKEND"
        message = "Market is closed (weekend). Opens Monday at 9:15 AM IST."

    return {
        "status": status,
        "message": message,
        "time_ist": now_ist.strftime("%I:%M %p IST, %A %d %b %Y"),
    }


# ─────────────────────────────────────────────
# 5. PORTFOLIO TRACKER DATABASE
# ─────────────────────────────────────────────

def init_portfolio_db():
    """Create the portfolio table if it doesn't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            buy_price REAL NOT NULL,
            buy_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_portfolio_transaction(symbol: str, quantity: float, buy_price: float, buy_date: str) -> tuple[bool, str]:
    """Add a stock transaction to the portfolio."""
    if quantity <= 0:
        return False, "❌ Quantity must be greater than zero."
    if buy_price <= 0:
        return False, "❌ Buy price must be greater than zero."
    
    # Validate stock symbol first
    valid, err_msg = validate_stock_symbol(symbol)
    if not valid:
        return False, err_msg
        
    init_portfolio_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO portfolio (symbol, quantity, buy_price, buy_date) VALUES (?, ?, ?, ?)",
            (symbol.upper().strip(), quantity, buy_price, buy_date)
        )
        conn.commit()
        return True, f"✅ Added {quantity} shares of {symbol.upper().strip()} to portfolio!"
    except Exception as e:
        return False, f"❌ Error adding transaction: {str(e)}"
    finally:
        conn.close()

def delete_portfolio_transaction(transaction_id: int):
    """Delete a transaction from portfolio."""
    init_portfolio_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()

def get_portfolio_transactions() -> list:
    """Get all transaction records ordered by buy date."""
    init_portfolio_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, symbol, quantity, buy_price, buy_date FROM portfolio ORDER BY buy_date DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_portfolio_holdings() -> dict:
    """Calculate aggregate quantities and average buy prices from transactions."""
    transactions = get_portfolio_transactions()
    holdings = {}
    for tid, symbol, qty, price, date in transactions:
        if symbol not in holdings:
            holdings[symbol] = {"quantity": 0.0, "total_cost": 0.0, "transactions": []}
        holdings[symbol]["quantity"] += qty
        holdings[symbol]["total_cost"] += qty * price
        holdings[symbol]["transactions"].append({
            "id": tid,
            "quantity": qty,
            "buy_price": price,
            "buy_date": date
        })
    
    # Calculate average price
    for symbol, data in list(holdings.items()):
        if data["quantity"] > 0:
            data["avg_price"] = data["total_cost"] / data["quantity"]
        else:
            del holdings[symbol]
            
    return holdings


# ─────────────────────────────────────────────
# 6. STOCK AND DATE VALIDATION HELPERS
# ─────────────────────────────────────────────

def validate_stock_symbol(symbol: str) -> tuple[bool, str]:
    """
    Validate if a stock symbol is valid and has data available on yfinance.
    Provides correction recommendations (e.g. suggesting .NS or .BO suffix).
    """
    symbol = symbol.strip().upper()
    if not symbol:
        return False, "❌ Stock symbol cannot be empty."
    
    try:
        ticker = yf.Ticker(symbol)
        # Try fetching historical info for 1 day
        hist = ticker.history(period="1d")
        if hist is None or hist.empty:
            if "." not in symbol:
                return False, f"❌ Invalid symbol '{symbol}'. Did you mean **{symbol}.NS** (NSE) or **{symbol}.BO** (BSE)?"
            return False, f"❌ Could not retrieve market data for '{symbol}'. Please check if the symbol is valid."
        return True, "Valid"
    except Exception as e:
        return False, f"❌ Error validating symbol: {str(e)}"

def validate_date_range(start_date, end_date) -> tuple[bool, str]:
    """
    Validate custom start and end date range.
    """
    if not start_date or not end_date:
        return False, "❌ Start and End dates are required."
    
    today = datetime.now().date()
    
    if start_date >= end_date:
        return False, "❌ Start Date must be strictly before End Date."
    if start_date > today:
        return False, "❌ Start Date cannot be in the future."
    if end_date > today:
        return False, "❌ End Date cannot be in the future."
    if (end_date - start_date).days > 365 * 30:
        return False, "❌ Date range cannot exceed 30 years."
        
    return True, "Valid"
