import warnings
warnings.filterwarnings("ignore")

import streamlit as st

st.set_page_config(page_title="Indian Stock Research Agent", layout="wide")

import yfinance as yf
import plotly.graph_objects as go
import os
from dotenv import load_dotenv

load_dotenv()

# --- Helper Functions ---
def get_stock_data(symbol, period="3mo"):
    try:
        hist = yf.download(symbol, period=period, auto_adjust=True, progress=False)
        if hist.empty:
            return None, None
        # Flatten multi-level columns
        hist.columns = hist.columns.get_level_values(0)
        info = yf.Ticker(symbol).info
        return hist, info
    except Exception as e:
        st.error(f"Error: {e}")
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
    fig.update_layout(title=f"{symbol} Stock Price", xaxis_title="Date",
                      yaxis_title="Price (INR)", template="plotly_dark")
    return fig

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
else:
    st.info("👈 Select a stock and click 'Fetch Data'")


st.markdown("---")
st.caption("⚠️ Educational purposes only. Not financial advice.")