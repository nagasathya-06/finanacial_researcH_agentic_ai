import yfinance as yf
ticker = yf.Ticker("RELIANCE.NS")
hist = ticker.history(period="3mo")
print(hist.head())