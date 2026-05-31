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

load_dotenv()

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
    except Exception as e:
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
    except Exception as e:
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
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name=symbol
    ))
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist['MA20'],
        line=dict(color='orange', width=1),
        name='MA20'
    ))
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist['MA50'],
        line=dict(color='blue', width=1),
        name='MA50'
    ))
    fig.update_layout(
        title=f"{symbol} Stock Price",
        xaxis_title="Date",
        yaxis_title="Price (INR)",
        template="plotly_dark",
        xaxis_rangeslider_visible=False
    )
    return fig, hist

# --- UI ---
st.title("🇮🇳 Indian Stock Research Agent")
st.caption("Track A | Financial Research AI Project")

st.sidebar.header("Stock Selection")
popular_stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "WIPRO.NS"]
selected = st.sidebar.selectbox("Choose a stock", popular_stocks)
custom = st.sidebar.text_input("Or enter custom symbol (e.g. SBIN.NS)")
symbol = custom if custom else selected
period = st.sidebar.selectbox("Period", ["1mo", "3mo", "6mo", "1y"])

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
            fig2.update_layout(
                title="Stock Comparison",
                template="plotly_dark",
                xaxis_rangeslider_visible=False
            )
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
                    timeout=30,
                    max_retries=1
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

st.markdown("---")
st.caption("⚠️ Educational purposes only. Not financial advice.")