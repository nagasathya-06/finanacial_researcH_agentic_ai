# 🇮🇳 Indian Stock Research Agent — AI-Powered Fintech App

> Track A | Financial Research AI Agent Project | Capabl

A Streamlit-based AI financial research assistant that analyzes Indian stock markets, fetches real-time data, performs news sentiment analysis, and answers questions using Google Gemini AI.

---

## 🚀 Live Demo
[Click here to view the deployed app](https://week1-agentic-ai.streamlit.app/)

---

## 📌 Features

### Week 1 and 2 — Foundation
- 📈 Real-time Indian stock data via Yahoo Finance (NSE/BSE)
- 🕯️ Interactive candlestick charts with Plotly
- 📊 Key metrics — Current Price, High, Low, % Change
- 🤖 AI chatbot powered by Google Gemini
- 🇮🇳 Indian stock support (RELIANCE.NS, TCS.NS, INFY.NS etc.)

### Week 3 and 4 — Sentiment Analysis
- 📰 Latest news fetching via NewsAPI
- 😊 Sentiment analysis using TextBlob (Positive / Neutral / Negative)
- 📉 Sentiment score displayed as a metric card
- ⚡ API caching to handle rate limits (5 min for stock, 10 min for news)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit + Plotly |
| Backend | Python + yFinance + TextBlob |
| AI | Google Gemini (gemini-flash-latest) |
| Framework | LangChain + LangChain Google GenAI |
| News API | NewsAPI.org |
| Deployment | Streamlit Cloud |

---

## ⚙️ Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/P-SAI-LEKHYA/finanacial_researcH_agentic_ai.git
cd finanacial_researcH_agentic_ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create `.env` file
GOOGLE_API_KEY=your_gemini_api_key
NEWS_API_KEY=your_newsapi_key

### 4. Run the app
```bash
python3 -m streamlit run app.py
```
