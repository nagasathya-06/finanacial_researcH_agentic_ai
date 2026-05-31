import os
import re
import warnings
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from PIL import ImageEnhance, ImageOps

warnings.filterwarnings("ignore")
# Ensure we load the project-local .env regardless of the current working directory.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

st.set_page_config(page_title="Financial Research + Spending Tracker", layout="wide")


SUPPORTED_CATEGORIES = [
    "Food",
    "Groceries",
    "Transport",
    "Shopping",
    "Bills & Utilities",
    "Rent & Housing",
    "Health",
    "Entertainment",
    "Education",
    "Investments",
    "Transfers",
    "Other",
]


@dataclass
class Expense:
    when: date
    description: str
    amount_inr: Decimal
    category: str
    source: str
    raw_text: str


def _safe_decimal(value: str) -> Optional[Decimal]:
    cleaned = value.strip().replace(",", "")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def categorize_expense(description: str, raw_text: str = "") -> str:
    haystack = f"{description} {raw_text}".lower()

    keyword_map: List[Tuple[str, List[str]]] = [
        ("Food", ["swiggy", "zomato", "restaurant", "cafe", "pizza", "biryani", "dine", "food"]),
        ("Groceries", ["dmart", "bigbasket", "grocer", "supermarket", "milk", "vegetable", "grocery"]),
        ("Transport", ["uber", "ola", "rapido", "metro", "bus", "fuel", "petrol", "diesel", "parking", "toll"]),
        ("Shopping", ["amazon", "flipkart", "myntra", "ajio", "meesho", "shopping", "order"]),
        ("Bills & Utilities", ["airtel", "jio", "vi ", "vodafone", "electric", "electricity", "gas", "water", "broadband", "recharge", "bill"]),
        ("Rent & Housing", ["rent", "maintenance", "society", "landlord"]),
        ("Health", ["pharmacy", "apollo", "1mg", "doctor", "hospital", "clinic", "medical"]),
        ("Entertainment", ["netflix", "prime", "hotstar", "spotify", "movie", "cinema", "game"]),
        ("Education", ["course", "udemy", "coursera", "byju", "unacademy", "fees", "tuition"]),
        ("Investments", ["sip", "mutual", "fund", "zerodha", "groww", "upstox", "etmoney", "ppf", "elss"]),
        ("Transfers", ["transfer", "sent", "self", "to self", "withdraw", "atm"]),
    ]

    for category, keywords in keyword_map:
        if any(k in haystack for k in keywords):
            return category
    return "Other"


def parse_amount_inr(text: str) -> Optional[Decimal]:
    lowered = (text or "").lower()

    # Collect candidates with context-based scoring.
    # Goal: pick the payment amount (often near "pay/paid/amount"), not balances or phone numbers.
    candidates: List[Tuple[int, Decimal]] = []

    # Prioritize explicit pay/paid/amount patterns.
    patterns = [
        r"pay\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.?[0-9]{0,2})",
        r"paid\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.?[0-9]{0,2})",
        r"amount\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.?[0-9]{0,2})",
        r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*\.?[0-9]{0,2})",
    ]

    for pat in patterns:
        for m in re.finditer(pat, lowered, flags=re.IGNORECASE):
            val = _safe_decimal(m.group(1))
            if val is None:
                continue

            # Filter obvious non-amounts.
            if val <= 0:
                continue
            # Ignore very large numbers (often phone/account refs) unless explicitly tagged.
            if val >= Decimal("10000000") and not any(k in pat for k in ["pay", "paid", "amount"]):
                continue

            start, end = m.span()
            ctx = lowered[max(0, start - 24) : min(len(lowered), end + 24)]

            score = 0
            if "pay" in ctx:
                score += 60
            if "paid" in ctx:
                score += 50
            if "amount" in ctx:
                score += 35
            if "₹" in m.group(0) or "rs" in m.group(0) or "inr" in m.group(0):
                score += 10
            if "balance" in ctx:
                score -= 30
            if "+91" in ctx or "mobile" in ctx or "phone" in ctx:
                score -= 20

            # Small nudge: prefer 2-6 digit amounts (typical UPI payments).
            digits = re.sub(r"\D", "", str(val))
            if 2 <= len(digits) <= 6:
                score += 5

            candidates.append((score, val))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return None


def _prep_for_ocr(image: Image.Image) -> List[Image.Image]:
    """Create a few safe variants for OCR; helps on phone screenshots."""
    variants: List[Image.Image] = []
    base = image.convert("RGB")
    variants.append(base)

    # Mild grayscale + contrast + upscaling.
    gray = ImageOps.grayscale(base)
    w, h = gray.size
    scale = 2
    gray2 = gray.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
    gray2 = ImageOps.autocontrast(gray2)
    gray2 = ImageEnhance.Contrast(gray2).enhance(1.8)
    gray2 = ImageEnhance.Sharpness(gray2).enhance(1.2)
    variants.append(gray2)

    # Light thresholding can help crisp UI text.
    thr = gray2.point(lambda x: 0 if x < 170 else 255, mode="1").convert("L")
    variants.append(thr)

    return variants


def parse_date(text: str) -> Optional[date]:
    # Try a few common formats; fall back to today.
    candidates = [
        r"\b(\d{2})[\-/](\d{2})[\-/](\d{4})\b",  # 30/05/2026
        r"\b(\d{4})[\-/](\d{2})[\-/](\d{2})\b",  # 2026-05-30
    ]
    for pat in candidates:
        match = re.search(pat, text)
        if not match:
            continue
        try:
            parts = [int(x) for x in match.groups()]
            if len(parts) == 3 and len(match.group(1)) == 4:
                yyyy, mm, dd = parts
            else:
                dd, mm, yyyy = parts
            return date(yyyy, mm, dd)
        except Exception:
            continue
    return None


def parse_description(text: str) -> str:
    # Heuristic: find a likely payee/merchant line.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = " ".join(lines)

    # Common UPI hints.
    upi_match = re.search(r"to\s+([A-Za-z0-9 ._\-]{3,50})", joined, flags=re.IGNORECASE)
    if upi_match:
        return upi_match.group(1).strip()

    # Fallback: first non-empty line truncated.
    return (lines[0] if lines else "Payment")[:60]


def ocr_with_tesseract(image: Image.Image) -> str:
    try:
        import pytesseract  # type: ignore
    except Exception as e:
        raise RuntimeError("pytesseract not installed") from e

    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    lang = os.getenv("TESSERACT_LANG", "eng").strip() or "eng"

    def _run(img: Image.Image, psm: int) -> str:
        config = f"--oem 3 --psm {psm}"
        return pytesseract.image_to_string(img, lang=lang, config=config)

    # If Tesseract binary isn't installed, pytesseract will throw a clear error.
    try:
        best_text = ""
        best_score = -1
        for variant in _prep_for_ocr(image):
            for psm in (6, 11):
                text = _run(variant, psm)
                score = len(re.findall(r"[A-Za-z0-9₹]", text or ""))
                if score > best_score:
                    best_score = score
                    best_text = text or ""

        return best_text
    except Exception as e:
        msg = str(e).lower()
        if "tesseract is not installed" in msg or "not in your path" in msg or "tesseractnotfounderror" in msg:
            raise RuntimeError(
                "Tesseract OCR engine not found.\n\n"
                "Install Tesseract for Windows, then either add it to PATH or set `TESSERACT_CMD` in your .env.\n"
                "Example (default install path):\n"
                "TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n\n"
                "After that, retry with OCR method 'Tesseract (local)' or 'Auto'."
            ) from e
        raise


def _is_gemini_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "quota exceeded" in msg
        or "resource_exhausted" in msg
        or "exceeded your current quota" in msg
        or "rate limit" in msg
        or "429" in msg
    )


def _friendly_gemini_quota_message(exc: Exception) -> str:
    return (
        "Gemini request blocked due to quota/rate limits (HTTP 429). "
        "This usually means your project/key has no usable quota (often free-tier limit = 0) "
        "or billing/quota is not enabled.\n\n"
        "Fix: open Google AI Studio / Google Cloud for the project behind your API key, "
        "check Gemini API quotas + billing/plan, then try again.\n"
        "Workaround: use OCR method ‘Tesseract (local)’ (no API).\n\n"
        f"Details: {exc}"
    )


def ocr_with_gemini(image: Image.Image) -> str:
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError("google-generativeai not installed") from e

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    preferred = os.getenv("GEMINI_OCR_MODEL", "gemini-1.5-flash")
    candidates = [
        preferred,
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-1.5-pro-latest",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-pro",
    ]
    prompt = (
        "Extract all readable text from this payment/UPI screenshot. "
        "Return plain text only (no markdown), preserving numbers exactly."
    )

    last_error: Optional[Exception] = None
    for name in [c for c in candidates if c]:
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content([prompt, image])
            return (response.text or "").strip()
        except Exception as e:
            last_error = e
            if _is_gemini_quota_error(e):
                raise RuntimeError(_friendly_gemini_quota_message(e)) from e
            msg = str(e)
            # Common case: model name not available for this API/version.
            if "404" in msg and "not found" in msg:
                continue
            # If it's not a model-not-found error, don't mask it.
            raise

    # As a last resort, try picking a compatible model from the API.
    try:
        models = list(genai.list_models())
        compatible = [
            m
            for m in models
            if getattr(m, "supported_generation_methods", None)
            and "generateContent" in list(getattr(m, "supported_generation_methods"))
        ]
        preferred_order = ["flash", "pro"]
        for keyword in preferred_order:
            match = next(
                (
                    m
                    for m in compatible
                    if keyword in str(getattr(m, "name", "")).lower()
                ),
                None,
            )
            if match is not None:
                model = genai.GenerativeModel(getattr(match, "name"))
                response = model.generate_content([prompt, image])
                return (response.text or "").strip()
    except Exception:
        pass

    raise RuntimeError(
        "No supported Gemini model found for OCR. "
        "Set GEMINI_OCR_MODEL to one of your available models (see list_models). "
        f"Last error: {last_error}"
    )


def extract_text(image: Image.Image, method: str) -> Tuple[str, List[str]]:
    warnings_out: List[str] = []
    method = method.lower()

    if method == "tesseract":
        return ocr_with_tesseract(image), warnings_out

    if method == "gemini":
        try:
            return ocr_with_gemini(image), warnings_out
        except Exception as e:
            if _is_gemini_quota_error(e):
                warnings_out.append("Gemini quota exceeded (429). Falling back to Tesseract (local) OCR.")
                return ocr_with_tesseract(image), warnings_out
            raise

    # Auto: prefer local OCR, fall back to Gemini.
    try:
        return ocr_with_tesseract(image), warnings_out
    except Exception as e:
        warnings_out.append(f"Tesseract OCR unavailable: {e}")

    try:
        text = ocr_with_gemini(image)
        warnings_out.append("Using Gemini OCR fallback (requires GOOGLE_API_KEY).")
        return text, warnings_out
    except Exception as e:
        # In Auto mode we don't hard-fail the UI; instead we surface a warning
        # and return empty text so the user can paste/edit manually.
        if _is_gemini_quota_error(e):
            warnings_out.append(
                "Gemini OCR blocked by quota/rate limits (HTTP 429). "
                "Since Tesseract (local) is unavailable too, OCR cannot run. "
                "Install/configure Tesseract (set `TESSERACT_CMD` in .env) or paste the transaction text manually."
            )
            return "", warnings_out
        warnings_out.append(f"Gemini OCR failed: {e}")
        return "", warnings_out


def build_advice(expenses: List[Expense], monthly_income_inr: Optional[Decimal], guru_style: str) -> str:
    if not expenses:
        return "Add at least one expense to get advice."

    df = pd.DataFrame(
        [
            {
                "date": e.when,
                "description": e.description,
                "amount": float(e.amount_inr),
                "category": e.category,
            }
            for e in expenses
        ]
    )

    totals = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    top_category = str(totals.iloc[0]["category"]) if not totals.empty else "Other"
    top_amount = Decimal(str(totals.iloc[0]["amount"])) if not totals.empty else Decimal("0")
    total_spend = Decimal(str(df["amount"].sum()))

    base = [
        f"Total logged spend: ₹{total_spend:.2f}.",
        f"Top category: {top_category} (₹{top_amount:.2f}).",
    ]

    if monthly_income_inr and monthly_income_inr > 0:
        spend_rate = (total_spend / monthly_income_inr) * Decimal("100")
        base.append(f"Spend vs income (rough): {spend_rate:.1f}%.")

    guru_style = guru_style.lower()
    if guru_style.startswith("warren"):
        tips = [
            "Keep it boring: automate long-term investing (e.g., broad low-cost funds) and avoid frequent trading.",
            "Create a buffer: maintain an emergency fund before increasing discretionary spends.",
        ]
    elif guru_style.startswith("ramit"):
        tips = [
            "Cut costs on things you don’t love; spend intentionally on what you do.",
            "Automate: fixed transfers to savings/investing on payday, then spend guilt-free within limits.",
        ]
    elif guru_style.startswith("robert") or "kiyosaki" in guru_style:
        tips = [
            "Track ‘assets vs liabilities’: prioritize building income-producing assets over lifestyle upgrades.",
            "Pay yourself first: set a savings/investing rule before discretionary categories expand.",
        ]
    else:
        tips = [
            "Aim for a simple split: needs vs wants vs savings/investments (adjust to your context).",
            "Review the top category and set a small weekly cap for the next 2 weeks.",
        ]

    category_nudge_map = {
        "Food": "Try batching meals or setting a weekly eating-out cap.",
        "Shopping": "Add a 24-hour delay rule for non-essential purchases.",
        "Transport": "Check if subscriptions/commute alternatives reduce recurring costs.",
        "Bills & Utilities": "Review recurring plans and renegotiate/recharge only as needed.",
    }
    nudge = category_nudge_map.get(top_category)
    if nudge:
        tips.insert(0, nudge)

    disclaimer = (
        "\n\n⚠️ Educational only — not financial or investment advice. "
        "For major decisions, consult a certified professional."
    )

    lines = base + [""] + [f"- {t}" for t in tips]
    return "\n".join(lines) + disclaimer


def _init_state() -> None:
    if "expenses" not in st.session_state:
        st.session_state["expenses"] = []
    if "extracted_text" not in st.session_state:
        st.session_state["extracted_text"] = ""
    if "week1_ticker" not in st.session_state:
        st.session_state["week1_ticker"] = "RELIANCE.NS"
    if "week1_period" not in st.session_state:
        st.session_state["week1_period"] = "3mo"
    if "week2_ocr_method" not in st.session_state:
        st.session_state["week2_ocr_method"] = "Auto"
    if "week2_guru_style" not in st.session_state:
        st.session_state["week2_guru_style"] = "Balanced (multi-guru)"
    if "week2_monthly_income" not in st.session_state:
        st.session_state["week2_monthly_income"] = ""


@st.cache_data(show_spinner=False, ttl=60 * 10)
def _fetch_price_history(ticker: str, period: str) -> pd.DataFrame:
    try:
        import yfinance as yf  # type: ignore
    except Exception as e:
        raise RuntimeError("Week 1 dependency missing: install 'yfinance' (see requirements.txt)") from e

    t = yf.Ticker(ticker)
    hist = t.history(period=period, auto_adjust=False)
    if hist is None or hist.empty:
        return pd.DataFrame()

    hist = hist.reset_index()
    # Normalize columns across yfinance versions.
    rename_map: Dict[str, str] = {}
    if "Date" in hist.columns:
        rename_map["Date"] = "Datetime"
    if "index" in hist.columns:
        rename_map["index"] = "Datetime"
    hist = hist.rename(columns=rename_map)
    if "Datetime" not in hist.columns:
        # Some versions already return 'Datetime'
        pass
    return hist


@st.cache_data(show_spinner=False, ttl=60 * 60)
def _fetch_ticker_info(ticker: str) -> Dict[str, Any]:
    try:
        import yfinance as yf  # type: ignore
    except Exception as e:
        raise RuntimeError("Week 1 dependency missing: install 'yfinance' (see requirements.txt)") from e

    t = yf.Ticker(ticker)
    info: Dict[str, Any] = {}
    try:
        info = dict(t.info or {})
    except Exception:
        info = {}
    return info


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    try:
        return f"{value * 100:.2f}%"
    except Exception:
        return "—"


def _build_week1_summary_text(ticker: str, hist: pd.DataFrame, info: Dict[str, Any]) -> str:
    if hist is None or hist.empty:
        return "No price history available for this ticker/period."

    df = hist.copy()
    if "Close" not in df.columns:
        return "Unexpected data format from yfinance (missing 'Close')."

    df = df.dropna(subset=["Close"])
    if df.empty:
        return "No valid close prices available."

    last_close = float(df["Close"].iloc[-1])
    first_close = float(df["Close"].iloc[0])
    pct_change = None
    if first_close != 0:
        pct_change = (last_close - first_close) / first_close

    high = float(df["High"].max()) if "High" in df.columns else None
    low = float(df["Low"].min()) if "Low" in df.columns else None
    name = info.get("shortName") or info.get("longName") or ticker
    currency = info.get("currency") or ""

    lines = [
        f"Ticker: {ticker}",
        f"Name: {name}",
        f"Period performance: {_format_pct(pct_change)}",
        f"Last close: {last_close:.2f} {currency}".strip(),
    ]
    if high is not None and low is not None:
        lines.append(f"Period range: {low:.2f} → {high:.2f} {currency}".strip())
    return "\n".join(lines)


def _gemini_week1_insight(ticker: str, summary: str) -> str:
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError("google-generativeai not installed") from e

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    preferred = os.getenv("GEMINI_TEXT_MODEL", "gemini-1.5-flash")
    candidates = [
        preferred,
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-1.5-pro-latest",
        "gemini-2.0-flash",
        "gemini-2.0-pro",
    ]
    prompt = (
        "You are a cautious financial research assistant. Provide educational-only insights. "
        "Do not give direct buy/sell commands. Keep it concise.\n\n"
        f"Here is a summary of recent data for {ticker}:\n{summary}\n\n"
        "Return:\n"
        "1) 3 bullet observations\n"
        "2) 3 questions to investigate next\n"
        "3) 2 risk notes\n"
        "Add a one-line disclaimer at the end."
    )

    last_error: Optional[Exception] = None
    for name in [c for c in candidates if c]:
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content(prompt)
            return (response.text or "").strip()
        except Exception as e:
            last_error = e
            if _is_gemini_quota_error(e):
                raise RuntimeError(_friendly_gemini_quota_message(e)) from e
            msg = str(e)
            if "404" in msg and "not found" in msg:
                continue
            raise

    try:
        models = list(genai.list_models())
        compatible = [
            m
            for m in models
            if getattr(m, "supported_generation_methods", None)
            and "generateContent" in list(getattr(m, "supported_generation_methods"))
        ]
        preferred_order = ["flash", "pro"]
        for keyword in preferred_order:
            match = next(
                (
                    m
                    for m in compatible
                    if keyword in str(getattr(m, "name", "")).lower()
                ),
                None,
            )
            if match is not None:
                model = genai.GenerativeModel(getattr(match, "name"))
                response = model.generate_content(prompt)
                return (response.text or "").strip()
    except Exception:
        pass

    raise RuntimeError(
        "No supported Gemini model found for text insights. "
        "Set GEMINI_TEXT_MODEL to one of your available models (see list_models). "
        f"Last error: {last_error}"
    )


def render_week1() -> None:
    st.subheader("Week 1 — Stock Research")
    st.caption("Market data via yfinance + optional AI insights (educational only)")

    ticker = str(st.session_state.get("week1_ticker", "RELIANCE.NS")).strip()
    period = str(st.session_state.get("week1_period", "3mo")).strip() or "3mo"

    if not ticker:
        st.info("Enter a ticker to start (e.g., RELIANCE.NS, AAPL, TSLA).")
        return

    with st.spinner("Fetching market data..."):
        hist = _fetch_price_history(ticker, period)
        info = _fetch_ticker_info(ticker)

    if hist.empty:
        st.warning("No data returned. Check the ticker symbol and try a different period.")
        return

    if "Datetime" in hist.columns:
        x = hist["Datetime"]
    else:
        # Fall back if yfinance returns a different index column
        x = hist.index

    st.markdown("### Price")
    if not all(col in hist.columns for col in ["Open", "High", "Low", "Close"]):
        st.warning("Candlestick chart unavailable (missing OHLC columns).")
    else:
        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=x,
                    open=hist["Open"],
                    high=hist["High"],
                    low=hist["Low"],
                    close=hist["Close"],
                )
            ]
        )
        fig.update_layout(title=f"{ticker} — Candlestick", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, width="stretch")

    # Quick metrics
    close_series = hist["Close"].dropna() if "Close" in hist.columns else pd.Series(dtype=float)
    if not close_series.empty:
        last_close = float(close_series.iloc[-1])
        prev_close = float(close_series.iloc[-2]) if len(close_series) >= 2 else last_close
        delta = last_close - prev_close
        high_val = float(hist["High"].max()) if "High" in hist.columns and not hist["High"].dropna().empty else None
        low_val = float(hist["Low"].min()) if "Low" in hist.columns and not hist["Low"].dropna().empty else None

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Last close", f"{last_close:.2f}", f"{delta:+.2f}")
        with m2:
            st.metric("Period high", f"{high_val:.2f}" if high_val is not None else "—")
        with m3:
            st.metric("Period low", f"{low_val:.2f}" if low_val is not None else "—")
        with m4:
            currency = info.get("currency") or ""
            st.metric("Currency", str(currency) if currency else "—")

    summary = _build_week1_summary_text(ticker, hist, info)
    st.markdown("### Snapshot")
    st.code(summary)

    with st.expander("Company / ticker details", expanded=False):
        if info:
            key_fields = [
                "shortName",
                "sector",
                "industry",
                "country",
                "currency",
                "marketCap",
                "trailingPE",
                "forwardPE",
                "dividendYield",
            ]
            rows = [{"field": k, "value": info.get(k)} for k in key_fields if k in info]
            df_info = pd.DataFrame(rows)
            if not df_info.empty and "value" in df_info.columns:
                df_info["value"] = df_info["value"].map(lambda v: "" if v is None else str(v))
            st.dataframe(df_info, width="stretch", hide_index=True)
        else:
            st.info("No additional info available.")

    st.markdown("### AI insights (optional)")
    st.caption("Uses your `GOOGLE_API_KEY` if set. Educational only.")
    if st.button("Generate AI insights", type="primary"):
        with st.spinner("Asking Gemini..."):
            try:
                insight = _gemini_week1_insight(ticker, summary)
                if insight:
                    st.text(insight)
                else:
                    st.warning("Gemini returned empty output.")
            except Exception as e:
                st.error(str(e))


def render_week2() -> None:
    st.subheader("Week 2 — Spending Tracker + Insights")
    st.caption("Screenshot expense extraction + categorization + spending insights")

    ocr_method = str(st.session_state.get("week2_ocr_method", "Auto"))
    guru_style = str(st.session_state.get("week2_guru_style", "Balanced (multi-guru)"))
    monthly_income = str(st.session_state.get("week2_monthly_income", ""))
    monthly_income_inr = _safe_decimal(monthly_income) if monthly_income.strip() else None

    tab1, tab2 = st.tabs(["📸 Add Expense", "📊 Dashboard"])

    with tab1:
        st.subheader("Upload a payment screenshot")
        uploaded = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "webp"])

        if uploaded is not None:
            image = Image.open(uploaded).convert("RGB")
            st.image(image, caption="Uploaded screenshot", width="stretch")

            col_a, col_b = st.columns([1, 2])
            with col_a:
                if st.button("Extract text", type="primary"):
                    method_key = {"auto": "auto", "tesseract (local)": "tesseract", "gemini (api)": "gemini"}
                    with st.spinner("Running OCR..."):
                        try:
                            text, ocr_warnings = extract_text(image, method_key[ocr_method.lower()])
                            st.session_state["extracted_text"] = text
                            for w in ocr_warnings:
                                st.warning(w)
                            if not text.strip():
                                st.warning("OCR returned empty text — try a clearer screenshot or a different method.")
                        except Exception as e:
                            st.error(str(e))

            with col_b:
                st.caption("You can edit the extracted text before parsing.")
                extracted_text = st.text_area("Extracted text", value=st.session_state["extracted_text"], height=220)
                st.session_state["extracted_text"] = extracted_text

            st.markdown("---")
            st.subheader("Parse and add to expenses")

            default_amount = parse_amount_inr(st.session_state["extracted_text"]) or Decimal("0")
            default_when = parse_date(st.session_state["extracted_text"]) or date.today()
            default_desc = parse_description(st.session_state["extracted_text"]) or "Payment"
            default_category = categorize_expense(default_desc, st.session_state["extracted_text"])

            with st.form("add_expense_form", clear_on_submit=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    when = st.date_input("Date", value=default_when)
                    amount_str = st.text_input("Amount (₹)", value=f"{default_amount}")
                with c2:
                    description = st.text_input("Description", value=default_desc)
                    category = st.selectbox(
                        "Category", SUPPORTED_CATEGORIES, index=SUPPORTED_CATEGORIES.index(default_category)
                    )
                with c3:
                    source = st.selectbox("Source", ["Screenshot"], index=0)

                submitted = st.form_submit_button("Add expense")
                if submitted:
                    amount = _safe_decimal(amount_str)
                    if amount is None or amount <= 0:
                        st.error("Please enter a valid positive amount.")
                    else:
                        st.session_state["expenses"].append(
                            Expense(
                                when=when,
                                description=description.strip() or "Payment",
                                amount_inr=amount,
                                category=category,
                                source=source,
                                raw_text=st.session_state["extracted_text"],
                            )
                        )
                        st.success("Expense added.")
        else:
            st.info("Upload a screenshot to extract an expense.")

        with st.expander("Other ways to add an expense", expanded=False):
            st.markdown("**Paste transaction text (SMS/UPI message)**")
            pasted = st.text_area("Transaction text", value="", height=160, key="pasted_text")
            if pasted.strip():
                default_amount = parse_amount_inr(pasted) or Decimal("0")
                default_when = parse_date(pasted) or date.today()
                default_desc = parse_description(pasted) or "Payment"
                default_category = categorize_expense(default_desc, pasted)
            else:
                default_amount = Decimal("0")
                default_when = date.today()
                default_desc = "Payment"
                default_category = "Other"

            with st.form("add_expense_form_text", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    when = st.date_input("Date", value=default_when, key="date_text")
                    amount_str = st.text_input("Amount (₹)", value=f"{default_amount}", key="amount_text")
                with c2:
                    description = st.text_input("Description", value=default_desc, key="desc_text")
                    category = st.selectbox(
                        "Category",
                        SUPPORTED_CATEGORIES,
                        index=SUPPORTED_CATEGORIES.index(default_category),
                        key="category_text",
                    )
                with c3:
                    source = st.selectbox("Source", ["Message/Text"], index=0)

                submitted = st.form_submit_button("Add expense (from text)")
                if submitted:
                    amount = _safe_decimal(amount_str)
                    if amount is None or amount <= 0:
                        st.error("Please enter a valid positive amount.")
                    else:
                        st.session_state["expenses"].append(
                            Expense(
                                when=when,
                                description=description.strip() or "Payment",
                                amount_inr=amount,
                                category=category,
                                source=source,
                                raw_text=pasted,
                            )
                        )
                        st.success("Expense added.")

            st.markdown("---")
            st.markdown("**Manual entry**")
            with st.form("add_expense_form_manual", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    when = st.date_input("Date", value=date.today(), key="date_manual")
                    amount_str = st.text_input("Amount (₹)", value="", key="amount_manual")
                with c2:
                    description = st.text_input("Description", value="", key="desc_manual")
                    auto_cat = categorize_expense(description)
                    category = st.selectbox(
                        "Category",
                        SUPPORTED_CATEGORIES,
                        index=SUPPORTED_CATEGORIES.index(auto_cat),
                        key="category_manual",
                    )
                with c3:
                    source = st.selectbox("Source", ["Manual"], index=0)

                submitted = st.form_submit_button("Add expense (manual)")
                if submitted:
                    amount = _safe_decimal(amount_str)
                    if amount is None or amount <= 0:
                        st.error("Please enter a valid positive amount.")
                    elif not description.strip():
                        st.error("Please enter a description.")
                    else:
                        st.session_state["expenses"].append(
                            Expense(
                                when=when,
                                description=description.strip(),
                                amount_inr=amount,
                                category=category,
                                source=source,
                                raw_text="",
                            )
                        )
                        st.success("Expense added.")

    with tab2:
        st.subheader("Expenses")
        expenses: List[Expense] = st.session_state["expenses"]

        if not expenses:
            st.info("No expenses yet. Add one from the 📸 Add Expense tab.")
        else:
            df = pd.DataFrame(
                [
                    {
                        "Date": e.when,
                        "Description": e.description,
                        "Amount (₹)": float(e.amount_inr),
                        "Category": e.category,
                        "Source": e.source,
                    }
                    for e in expenses
                ]
            ).sort_values("Date", ascending=False)

            # Streamlit/Arrow is stricter with mixed object types.
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

            # Small summary to make the dashboard feel nicer.
            total_spend = float(df["Amount (₹)"].sum()) if "Amount (₹)" in df.columns else 0.0
            by_cat = (
                df.groupby("Category", as_index=False)["Amount (₹)"]
                .sum()
                .sort_values("Amount (₹)", ascending=False)
            )
            top_cat = str(by_cat.iloc[0]["Category"]) if not by_cat.empty else "—"
            top_amt = float(by_cat.iloc[0]["Amount (₹)"]) if not by_cat.empty else 0.0
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Total spend", f"₹{total_spend:,.2f}")
            with m2:
                st.metric("Top category", top_cat)
            with m3:
                st.metric("Top category spend", f"₹{top_amt:,.2f}")

            st.dataframe(df, width="stretch", hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                fig = px.pie(by_cat, names="Category", values="Amount (₹)", title="Spend by category")
                st.plotly_chart(fig, width="stretch")

            with c2:
                st.subheader("Insights")
                advice = build_advice(expenses, monthly_income_inr, guru_style)
                st.text(advice)

            st.markdown("---")
            if st.button("Clear all expenses", type="secondary"):
                st.session_state["expenses"] = []
                st.session_state["extracted_text"] = ""
                st.rerun()



_init_state()

st.title("Financial Research + Spending Tracker (Week 1 + Week 2)")
st.caption("Stock research + personal spending tracker (educational only)")

with st.sidebar:
    st.header("Controls")

    st.caption(f"GOOGLE_API_KEY: {'set' if bool(os.getenv('GOOGLE_API_KEY')) else 'not set'}")

    with st.expander("Week 1 settings", expanded=True):
        st.text_input("Ticker", key="week1_ticker")
        st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "5y"], key="week1_period")

    with st.expander("Week 2 settings", expanded=True):
        st.selectbox("OCR method", ["Auto", "Tesseract (local)", "Gemini (API)"], key="week2_ocr_method")
        st.selectbox(
            "Insights style",
            ["Balanced (multi-guru)", "Warren Buffett", "Ramit Sethi", "Robert Kiyosaki"],
            key="week2_guru_style",
        )
        st.text_input("Monthly income (₹) (optional)", key="week2_monthly_income")

main_tab1, main_tab2 = st.tabs(["📈 Week 1: Stock Research", "🧾 Week 2: Spending Tracker"])

with main_tab1:
    render_week1()

with main_tab2:
    render_week2()
