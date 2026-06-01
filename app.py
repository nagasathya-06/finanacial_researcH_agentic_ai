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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# ── Week 5-6 imports ──────────────────────────────────────────────────────────
from week56_features import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    get_fundamentals,
    INDIAN_SECTORS, get_sector_comparison_data, plot_sector_comparison, get_sector_metrics_table,
    get_market_status,
)

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# ORIGINAL WEEK 1-4 FUNCTIONS (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_stock_data(symbol, period="3mo"):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist is None or hist.empty:
            hist = yf.download(symbol, period=period, auto_adjust=True, progress=False, ignore_tz=True)
        if hist.empty:
            return None, None
        hist.columns = hist.columns.get_level_values(0)
        return hist, None
    except Exception:
        return None, None

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
            label = "🟢 Positive" if sentiment > 0.1 else ("🔴 Negative" if sentiment < -0.1 else "🟡 Neutral")
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

def plot_stock_chart(hist, symbol):
    hist = add_technical_indicators(hist)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'],
        name=symbol
    ))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['MA50'], line=dict(color='blue', width=1), name='MA50'))
    fig.update_layout(
        title=f"{symbol} Stock Price",
        xaxis_title="Date", yaxis_title="Price (INR)",
        template="plotly_dark", xaxis_rangeslider_visible=False
    )
    return fig, hist


# ─────────────────────────────────────────────────────────────────────────────
# UI — HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.title("🇮🇳 Indian Stock Research Agent")
st.caption("Track A | Weeks 1-6 | Financial Research AI Project")

# ── Market Status Banner (Week 5-6 addition) ─────────────────────────────────
market = get_market_status()
st.info(f"**{market['status']}** — {market['message']}  \n🕐 Current time: {market['time_ist']}")

# ─────────────────────────────────────────────────────────────────────────────
# NAVIGATION TABS
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Stock Analysis",
    "⭐ My Watchlist",
    "📊 Fundamentals",
    "🏭 Sector Comparison",
])


# ═══════════════════════════════════════════════════════════════════════
# TAB 1: STOCK ANALYSIS (original weeks 1-4 content, unchanged)
# ═══════════════════════════════════════════════════════════════════════
with tab1:
    st.sidebar.header("Stock Selection")
    popular_stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "WIPRO.NS"]
    selected = st.sidebar.selectbox("Choose a stock", popular_stocks)
    custom = st.sidebar.text_input("Or enter custom symbol (e.g. SBIN.NS)")
    symbol = custom if custom else selected
    period = st.sidebar.selectbox("Period", ["1mo", "3mo", "6mo", "1y"])

    # ── Watchlist add button in sidebar ──────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("⭐ Watchlist")
    if st.sidebar.button("Add current stock to Watchlist"):
        ok, msg = add_to_watchlist(symbol)
        st.sidebar.success(msg) if ok else st.sidebar.warning(msg)

    if st.sidebar.button("Fetch Data"):
        with st.spinner("Fetching stock data..."):
            hist, info = get_stock_data(symbol, period)
            if hist is not None:
                st.session_state['hist'] = hist
                st.session_state['symbol'] = symbol
                company_name = symbol.replace(".NS", "").replace(".BO", "")
                news, avg_score = get_news_sentiment(company_name)
                st.session_state['news'] = news
                st.session_state['avg_score'] = avg_score
                st.success(f"Data loaded for {symbol}")
            else:
                st.error("Could not fetch data. Check the symbol.")

    if 'hist' in st.session_state:
        hist = st.session_state['hist']
        symbol = st.session_state['symbol']
        news = st.session_state.get('news', [])
        avg_score = st.session_state.get('avg_score', 0)

        current_price = float(hist['Close'].iloc[-1])
        prev_price = float(hist['Close'].iloc[-2])
        change_pct = ((current_price - prev_price) / prev_price) * 100
        sentiment_label = "🟢 Positive" if avg_score > 0.1 else ("🔴 Negative" if avg_score < -0.1 else "🟡 Neutral")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"₹{current_price:.2f}", f"{change_pct:.2f}%")
        col2.metric("High", f"₹{float(hist['High'].max()):.2f}")
        col3.metric("Low", f"₹{float(hist['Low'].min()):.2f}")
        col4.metric("News Sentiment", sentiment_label, f"Score: {avg_score}")

        fig, hist_with_indicators = plot_stock_chart(hist, symbol)
        st.plotly_chart(fig, use_container_width=True)

        rsi_value = float(hist_with_indicators['RSI'].iloc[-1])
        rsi_label = "Overbought 🔴" if rsi_value > 70 else ("Oversold 🟢" if rsi_value < 30 else "Neutral 🟡")
        st.metric("RSI (14)", f"{rsi_value:.2f}", rsi_label)

        st.subheader("📰 Latest News & Sentiment")
        if news:
            for article in news:
                with st.expander(f"{article['sentiment']} — {article['title']}"):
                    st.write(f"Sentiment Score: {article['score']}")
                    st.write(f"[Read Full Article]({article['url']})")
        else:
            st.info("No news found or NEWS_API_KEY missing.")

        st.subheader("📊 Compare Stocks")
        compare_symbol = st.text_input("Enter another stock to compare (e.g. TCS.NS)")
        if st.button("Compare") and compare_symbol:
            hist2, _ = get_stock_data(compare_symbol, period)
            if hist2 is not None:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name=symbol))
                fig2.add_trace(go.Scatter(x=hist2.index, y=hist2['Close'], name=compare_symbol))
                fig2.update_layout(title="Stock Comparison", template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.error("Could not fetch comparison stock.")

        st.subheader("💬 Ask AI About This Stock")
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
    st.header("⭐ My Watchlist")
    st.write("Save your favourite Indian stocks here. Their latest prices are fetched automatically.")

    # Add a stock manually from this tab too
    col_a, col_b = st.columns([3, 1])
    with col_a:
        new_stock = st.text_input("Add stock to watchlist (e.g. SBIN.NS)", key="wl_add")
    with col_b:
        st.write("")  # spacer
        st.write("")  # spacer
        if st.button("➕ Add"):
            if new_stock:
                ok, msg = add_to_watchlist(new_stock)
                st.success(msg) if ok else st.warning(msg)
            else:
                st.warning("Please enter a stock symbol first.")

    st.markdown("---")

    watchlist = get_watchlist()
    if not watchlist:
        st.info("Your watchlist is empty. Add stocks using the button above or from the sidebar in Stock Analysis tab.")
    else:
        st.subheader(f"You have {len(watchlist)} stock(s) saved:")
        for symbol_wl, added_on in watchlist:
            with st.expander(f"📌 {symbol_wl}  —  Added: {added_on}"):
                with st.spinner(f"Loading {symbol_wl}..."):
                    hist_wl, _ = get_stock_data(symbol_wl, "1mo")
                    if hist_wl is not None:
                        price = float(hist_wl['Close'].iloc[-1])
                        prev  = float(hist_wl['Close'].iloc[-2])
                        chg   = ((price - prev) / prev) * 100
                        arrow = "🔺" if chg >= 0 else "🔻"
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Price", f"₹{price:.2f}", f"{arrow} {chg:.2f}%")
                        col2.metric("1M High", f"₹{float(hist_wl['High'].max()):.2f}")
                        col3.metric("1M Low",  f"₹{float(hist_wl['Low'].min()):.2f}")
                    else:
                        st.warning("Could not load price data for this stock.")

                if st.button(f"🗑️ Remove {symbol_wl}", key=f"remove_{symbol_wl}"):
                    ok, msg = remove_from_watchlist(symbol_wl)
                    st.success(msg) if ok else st.warning(msg)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# TAB 3: FUNDAMENTAL ANALYSIS  (Week 5-6 — new)
# ═══════════════════════════════════════════════════════════════════════
with tab3:
    st.header("📊 Fundamental Analysis")
    st.write("Get key financial metrics for any Indian stock — P/E ratio, EPS, debt levels, growth, and more.")

    col_sym, col_btn = st.columns([3, 1])
    with col_sym:
        fund_symbol = st.text_input(
            "Enter stock symbol (e.g. RELIANCE.NS, TCS.NS, SBIN.NS)",
            placeholder="RELIANCE.NS",
            key="fund_input"
        )
    with col_btn:
        st.write(""); st.write("")
        fetch_fund = st.button("🔍 Analyse")

    if fetch_fund and fund_symbol:
        with st.spinner(f"Fetching fundamentals for {fund_symbol}..."):
            data = get_fundamentals(fund_symbol)

        if "error" in data:
            st.error(data["error"])
        else:
            st.subheader(f"🏢 {data.get('Company Name', fund_symbol)}")
            badge_col1, badge_col2 = st.columns(2)
            badge_col1.info(f"**Sector:** {data.get('Sector', 'N/A')}")
            badge_col2.info(f"**Industry:** {data.get('Industry', 'N/A')}")

            st.markdown("#### 💰 Valuation")
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Market Cap",    data["Market Cap"])
            v2.metric("Current Price", data["Current Price"])
            v3.metric("P/E Ratio",     data["P/E Ratio"])
            v4.metric("Forward P/E",   data["Forward P/E"])

            st.markdown("#### 📈 Performance")
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("EPS (TTM)",       data["EPS (TTM)"])
            p2.metric("Return on Equity",data["Return on Equity"])
            p3.metric("Revenue Growth",  data["Revenue Growth"])
            p4.metric("Profit Margin",   data["Profit Margin"])

            st.markdown("#### 🛡️ Risk & Range")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("52W High",      data["52W High"])
            r2.metric("52W Low",       data["52W Low"])
            r3.metric("Debt/Equity",   data["Debt/Equity"])
            r4.metric("Beta",          data["Beta"])

            st.markdown("#### 💵 Dividend")
            st.metric("Dividend Yield", data["Dividend Yield"])

            st.markdown("---")
            st.caption("ℹ️ Data sourced from Yahoo Finance. P/E and EPS are trailing twelve months (TTM). Not investment advice.")

    elif fetch_fund:
        st.warning("Please enter a stock symbol.")

    # Quick fundamentals insight guide for beginners
    with st.expander("📖 What do these terms mean? (Beginner Guide)"):
        st.markdown("""
| Term | What it means | Good range (rough guide) |
|------|--------------|--------------------------|
| **P/E Ratio** | How much you pay per ₹1 of earnings. High P/E = market expects growth. | 10–25 for most sectors |
| **EPS** | Earnings Per Share — profit divided by number of shares | Higher is better |
| **Debt/Equity** | How much debt vs. own money the company uses | < 1.0 is generally safer |
| **Return on Equity** | How efficiently company uses shareholder money | > 15% is good |
| **Beta** | How volatile the stock is vs the market. Beta > 1 = more volatile | Depends on your risk tolerance |
| **52W High/Low** | Highest and lowest price in the past 52 weeks | Shows current price context |
        """)


# ═══════════════════════════════════════════════════════════════════════
# TAB 4: SECTOR COMPARISON  (Week 5-6 — new)
# ═══════════════════════════════════════════════════════════════════════
with tab4:
    st.header("🏭 Indian Sector Comparison")
    st.write("Compare how stocks within the same sector have performed relative to each other.")

    sector_choice = st.selectbox(
        "Choose a sector to compare:",
        list(INDIAN_SECTORS.keys()),
        key="sector_select"
    )

    # Let user customise which stocks to include
    default_symbols = INDIAN_SECTORS[sector_choice]
    chosen_symbols = st.multiselect(
        "Stocks to include (you can add/remove):",
        options=default_symbols,
        default=default_symbols[:4],   # show first 4 by default
        key="sector_symbols"
    )

    # Allow adding a custom stock to the comparison
    custom_sector_stock = st.text_input(
        "Add a custom stock to this comparison (optional, e.g. LTIM.NS):",
        key="custom_sector"
    )
    if custom_sector_stock:
        chosen_symbols = list(chosen_symbols) + [custom_sector_stock.upper()]

    sector_period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=1, key="sector_period")

    if st.button("📊 Compare Sector") and chosen_symbols:
        with st.spinner(f"Loading data for {len(chosen_symbols)} stocks..."):
            df_norm = get_sector_comparison_data(chosen_symbols, period=sector_period)

        if df_norm.empty:
            st.error("Could not load data for the selected stocks.")
        else:
            fig_sector = plot_sector_comparison(df_norm, sector_choice)
            st.plotly_chart(fig_sector, use_container_width=True)

            st.subheader("📋 Quick Metrics Table")
            st.caption("Loading individual metrics may take a moment...")
            with st.spinner("Fetching metrics..."):
                metrics_df = get_sector_metrics_table(chosen_symbols)

            if not metrics_df.empty:
                # Colour 1Y change: green for positive, red for negative
                def style_change(val):
                    try:
                        color = "green" if float(val) >= 0 else "red"
                        return f"color: {color}"
                    except Exception:
                        return ""

                styled = metrics_df.style.applymap(style_change, subset=["1Y Change (%)"])
                st.dataframe(styled, use_container_width=True)
            else:
                st.info("Could not load metrics table.")

    elif not chosen_symbols:
        st.warning("Please select at least one stock.")

    st.markdown("---")
    st.caption("💡 Tip: The chart normalises all stocks to a base of 100 so you can compare % growth — not absolute prices.")


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("⚠️ Educational purposes only. Not financial advice. Data sourced from Yahoo Finance & NewsAPI.")
