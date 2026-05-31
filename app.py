import warnings
warnings.filterwarnings("ignore")

import streamlit as st
st.set_page_config(page_title="Indian Stock Research Agent", layout="wide")

import yfinance as yf
import plotly.graph_objects as go
import os
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
            hist = yf.download(
                symbol,
                period=period,
                auto_adjust=True,
                progress=False,
                ignore_tz=True
            )
        if hist.empty:
            return None, None
        hist.columns = hist.columns.get_level_values(0)
        return hist, None
    except Exception as e:
        return None, None
def plot_stock_chart(hist, symbol):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name=symbol
    ))
    fig.update_layout(
        title=f"{symbol} Stock Price",
        xaxis_title="Date",
        yaxis_title="Price (INR)",
        template="plotly_dark",
        xaxis_rangeslider_visible=False  # removes the mini chart below
    )
    return fig

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
            st.session_state['info'] = info
            st.session_state['symbol'] = symbol
            st.success(f"Data loaded for {symbol}")
        else:
            st.error("Could not fetch data. Check the symbol.")

if 'hist' in st.session_state:
    hist = st.session_state['hist']
    symbol = st.session_state['symbol']

    col1, col2, col3 = st.columns(3)
    current_price = float(hist['Close'].iloc[-1])
    prev_price = float(hist['Close'].iloc[-2])
    change_pct = ((current_price - prev_price) / prev_price) * 100

    col1.metric("Current Price", f"₹{current_price:.2f}", f"{change_pct:.2f}%")
    col2.metric("High", f"₹{float(hist['High'].max()):.2f}")
    col3.metric("Low", f"₹{float(hist['Low'].min()):.2f}")

    st.plotly_chart(plot_stock_chart(hist, symbol), use_container_width=True)

    st.subheader("💬 Ask AI About This Stock")
    user_question = st.text_input("Ask a question (e.g. Is this stock trending up?)")

    if st.button("Ask") and user_question:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            st.error("API key not found. Check your .env file.")
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