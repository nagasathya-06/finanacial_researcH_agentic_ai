from fpdf import FPDF
from datetime import datetime

def clean_rupee(val):
    """
    Recursively replaces unicode rupee symbol '₹' with standard 'Rs. '
    and filters out any unsupported unicode characters to prevent FPDFUnicodeEncodingException.
    """
    if isinstance(val, str):
        # Replace the Indian Rupee symbol
        val = val.replace("₹", "Rs. ")
        # Also clean common unicode dashes and quotes
        val = val.replace("—", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
        # Encode to CP1252 (FPDF default) ignoring errors, then decode back
        try:
            return val.encode("cp1252", errors="ignore").decode("cp1252")
        except Exception:
            # Fallback if encoding/decoding fails for some reason
            return "".join(c for c in val if ord(c) < 128)
    if isinstance(val, dict):
        return {k: clean_rupee(v) for k, v in val.items()}
    if isinstance(val, list):
        return [clean_rupee(i) for i in val]
    if isinstance(val, tuple):
        return tuple(clean_rupee(i) for i in val)
    return val

class FinancialPDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 14)
        self.set_text_color(142, 112, 76)  # Nifty Gold (Dark)
        self.cell(0, 10, "INDIAN STOCK RESEARCH TERMINAL", ln=1, align="L")
        self.set_draw_color(142, 112, 76)
        self.line(10, 20, 200, 20)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "CONFIDENTIAL & PROPRIETARY | For educational use only. Not investment advice.", align="L")
        self.set_x(-30)
        self.cell(20, 10, f"Page {self.page_no()}", align="R")

def generate_stock_report_pdf(symbol: str, info: dict, rsi_val: float, rsi_label: str, sentiment_label: str, sentiment_score: float) -> bytes:
    # Clean rupee symbols and other unicode characters before formatting
    symbol = clean_rupee(symbol)
    info = clean_rupee(info)
    rsi_label = clean_rupee(rsi_label)
    sentiment_label = clean_rupee(sentiment_label)

    pdf = FinancialPDF()
    pdf.add_page()
    
    # Title Block
    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(30, 41, 59) # Slate 800
    pdf.cell(0, 12, f"Research Report: {symbol}", ln=1)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(100, 116, 139) # Slate 500
    date_str = datetime.now().strftime("%B %d, %Y %I:%M %p")
    pdf.cell(0, 6, f"Generated on: {date_str} IST", ln=1)
    pdf.ln(5)
    
    # Profile Section
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Company Overview", ln=1)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(51, 65, 85)
    
    comp_name = info.get("Company Name", symbol)
    sector = info.get("Sector", "N/A")
    industry = info.get("Industry", "N/A")
    mcap = info.get("Market Cap", "N/A")
    
    pdf.cell(50, 6, "Company Name:", border="B")
    pdf.cell(0, 6, comp_name, border="B", ln=1)
    pdf.cell(50, 6, "Sector:", border="B")
    pdf.cell(0, 6, sector, border="B", ln=1)
    pdf.cell(50, 6, "Industry:", border="B")
    pdf.cell(0, 6, industry, border="B", ln=1)
    pdf.cell(50, 6, "Market Capitalization:", border="B")
    pdf.cell(0, 6, mcap, border="B", ln=1)
    pdf.ln(8)
    
    # Financial Valuation Section
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Key Valuation & Profitability Metrics", ln=1)
    
    # Draw a table
    # Headers
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 6, " Metric Name", border=1, fill=True)
    pdf.cell(35, 6, " Value", border=1, fill=True)
    pdf.cell(60, 6, " Metric Name", border=1, fill=True)
    pdf.cell(35, 6, " Value", border=1, fill=True, ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)
    
    metrics_left = [
        ("Current Price", info.get("Current Price", "N/A")),
        ("P/E Ratio (TTM)", info.get("P/E Ratio", "N/A")),
        ("Forward P/E", info.get("Forward P/E", "N/A")),
        ("52-Week High", info.get("52W High", "N/A")),
        ("52-Week Low", info.get("52W Low", "N/A")),
    ]
    metrics_right = [
        ("EPS (TTM)", info.get("EPS (TTM)", "N/A")),
        ("Return on Equity (ROE)", info.get("Return on Equity", "N/A")),
        ("Profit Margin", info.get("Profit Margin", "N/A")),
        ("Debt/Equity Ratio", info.get("Debt/Equity", "N/A")),
        ("Beta Coefficient", info.get("Beta", "N/A")),
    ]
    
    for i in range(max(len(metrics_left), len(metrics_right))):
        n_l, v_l = metrics_left[i] if i < len(metrics_left) else ("", "")
        n_r, v_r = metrics_right[i] if i < len(metrics_right) else ("", "")
        
        pdf.cell(60, 6, f" {n_l}", border=1)
        pdf.cell(35, 6, f" {v_l}", border=1)
        pdf.cell(60, 6, f" {n_r}", border=1)
        pdf.cell(35, 6, f" {v_r}", border=1, ln=1)
    
    pdf.ln(8)
    
    # Technical & Sentiment Analysis
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Technical & News Sentiment Analysis", ln=1)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(51, 65, 85)
    
    # RSI Row
    pdf.cell(60, 6, "14-Day RSI Value:", border="B")
    rsi_color = (0, 138, 94) if "OVERSOLD" in rsi_label else ((217, 56, 86) if "OVERBOUGHT" in rsi_label else (30, 41, 59))
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*rsi_color)
    pdf.cell(0, 6, f"{rsi_val:.2f} ({rsi_label})", border="B", ln=1)
    
    # Sentiment Row
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(51, 65, 85)
    pdf.cell(60, 6, "News Sentiment Classification:", border="B")
    
    sent_color = (0, 138, 94) if "Positive" in sentiment_label or "BULLISH" in sentiment_label else ((217, 56, 86) if "Negative" in sentiment_label or "BEARISH" in sentiment_label else (30, 41, 59))
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*sent_color)
    pdf.cell(0, 6, f"{sentiment_label} (Score: {sentiment_score:+.2f})", border="B", ln=1)
    
    pdf.ln(15)
    
    # Investment Advisory Section
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(142, 112, 76) # Gold
    pdf.cell(0, 6, "AI FINANCIAL ASSISTANT SUMMARY", ln=1)
    
    pdf.set_font("helvetica", "I", 9)
    pdf.set_text_color(100, 116, 139)
    
    summary_text = (
        f"The technical indicators for {symbol} indicate a 14-day RSI of {rsi_val:.2f}, classified as {rsi_label}. "
        f"The news sentiment dashboard aggregates recent publications with a {sentiment_label.lower()} sentiment "
        f"(score of {sentiment_score:+.2f}). Fundamental metrics suggest a market capitalization of {mcap} with a "
        f"P/E ratio of {info.get('P/E Ratio', 'N/A')}. This report is generated programmatically. Please consult a SEBI registered "
        f"financial adviser before making any investment decisions."
    )
    pdf.multi_cell(0, 5, summary_text)
    
    return bytes(pdf.output())

def generate_portfolio_report_pdf(holdings: dict, transactions: list, summary_stats: dict) -> bytes:
    # Clean rupee symbols and other unicode characters before formatting
    holdings = clean_rupee(holdings)
    transactions = clean_rupee(transactions)
    summary_stats = clean_rupee(summary_stats)

    pdf = FinancialPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 12, "Portfolio Valuation Report", ln=1)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    date_str = datetime.now().strftime("%B %d, %Y %I:%M %p")
    pdf.cell(0, 6, f"As of: {date_str} IST", ln=1)
    pdf.ln(5)
    
    # Overall Performance Cards
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Portfolio Summary Metrics", ln=1)
    
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 247, 250)
    pdf.cell(45, 8, " Total Cost", border=1, fill=True)
    pdf.cell(45, 8, " Current Value", border=1, fill=True)
    pdf.cell(45, 8, " Absolute Return", border=1, fill=True)
    pdf.cell(45, 8, " Percentage Return", border=1, fill=True, ln=1)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(51, 65, 85)
    pdf.cell(45, 8, f" INR {summary_stats['total_cost']:,.2f}", border=1)
    pdf.cell(45, 8, f" INR {summary_stats['total_value']:,.2f}", border=1)
    
    ret_color = (0, 138, 94) if summary_stats['total_return_abs'] >= 0 else (217, 56, 86)
    pdf.set_text_color(*ret_color)
    pdf.cell(45, 8, f" INR {summary_stats['total_return_abs']:+,.2f}", border=1)
    pdf.cell(45, 8, f" {summary_stats['total_return_pct']:+,.2f}%", border=1, ln=1)
    pdf.ln(8)
    
    # Holdings Table
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Current Holdings", ln=1)
    
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(30, 7, " Ticker", border=1, fill=True)
    pdf.cell(20, 7, " Quantity", border=1, fill=True, align="R")
    pdf.cell(30, 7, " Avg Price", border=1, fill=True, align="R")
    pdf.cell(30, 7, " Current Price", border=1, fill=True, align="R")
    pdf.cell(35, 7, " Cost Basis", border=1, fill=True, align="R")
    pdf.cell(35, 7, " Current Value", border=1, fill=True, align="R", ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)
    
    for symbol, data in holdings.items():
        pdf.cell(30, 7, f" {symbol}", border=1)
        pdf.cell(20, 7, f"{data['quantity']:,.1f} ", border=1, align="R")
        pdf.cell(30, 7, f"Rs {data['avg_price']:,.2f} ", border=1, align="R")
        pdf.cell(30, 7, f"Rs {data['current_price']:,.2f} ", border=1, align="R")
        pdf.cell(35, 7, f"Rs {data['total_cost']:,.2f} ", border=1, align="R")
        pdf.cell(35, 7, f"Rs {data['current_value']:,.2f} ", border=1, align="R", ln=1)
        
    pdf.ln(8)
    
    # Recent Transactions
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Transaction History", ln=1)
    
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(15, 6, " ID", border=1, fill=True)
    pdf.cell(35, 6, " Ticker", border=1, fill=True)
    pdf.cell(30, 6, " Date", border=1, fill=True)
    pdf.cell(35, 6, " Quantity Purchased", border=1, fill=True, align="R")
    pdf.cell(45, 6, " Buy Price", border=1, fill=True, align="R", ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)
    for t_id, symbol, qty, price, date in transactions[:15]:  # limit to top 15
        pdf.cell(15, 6, f" #{t_id}", border=1)
        pdf.cell(35, 6, f" {symbol}", border=1)
        pdf.cell(30, 6, f" {date}", border=1)
        pdf.cell(35, 6, f"{qty:,.2f} ", border=1, align="R")
        pdf.cell(45, 6, f"Rs {price:,.2f} ", border=1, align="R", ln=1)
        
    if len(transactions) > 15:
        pdf.cell(0, 6, f"... and {len(transactions) - 15} more transactions.", ln=1, align="C")
        
    return bytes(pdf.output())
