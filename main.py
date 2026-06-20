from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAW_CHAT_ID = os.getenv("RAW_CHAT_ID")
FILTERED_CHAT_ID = os.getenv("FILTERED_CHAT_ID", RAW_CHAT_ID)
FILTER_SCORE_MIN = 1

print("TOKEN loaded:", TELEGRAM_BOT_TOKEN is not None)
print("RAW_CHAT_ID:", RAW_CHAT_ID)
print("FILTERED_CHAT_ID:", FILTERED_CHAT_ID)

from fastapi import BackgroundTasks, FastAPI, Request
import requests
import json
import os

app = FastAPI()


def load_portfolio():
    try:
        with open("portfolio.json", "r") as f:
            return json.load(f)
    except:
        return {}

def send_telegram(message, chat_id):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        print("Missing Telegram token or chat_id")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(url, json={
        "chat_id": chat_id,
        "text": message
    })

    print("Telegram status:", response.status_code)
    print("Telegram response:", response.text)
    print("Sent to chat_id:", chat_id)

    return response.ok


def score_alert(ticker, signal, price=None):
    signal_l = signal.lower()
    score = 0
    reasons = []

    # Stronger signals
    if "rsi crossed" in signal_l or "rsi cross" in signal_l:
        score += 2
        reasons.append("RSI crossed MA")

    if "rsi rising" in signal_l:
        score += 2
        reasons.append("RSI rising")

    if "ema21 reclaim" in signal_l or "above ema21" in signal_l:
        score += 2
        reasons.append("EMA21 reclaim")

    if "volume" in signal_l or "unusual volume" in signal_l:
        score += 2
        reasons.append("Volume confirmation")

    if "bullish divergence" in signal_l:
        score += 3
        reasons.append("Bullish divergence")

    if "bottom" in signal_l or "reversal" in signal_l:
        score += 2
        reasons.append("Possible reversal")

    # Weaker / warning signals
    if "below ema21" in signal_l:
        score -= 1
        reasons.append("Below EMA21")

    if "rsi falling" in signal_l or "weakening" in signal_l:
        score -= 2
        reasons.append("RSI weakening")

    if "trim" in signal_l or "peak warning" in signal_l:
        score -= 1
        reasons.append("Peak/trim warning")

    return score, reasons


def first_available(data, *keys):
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def format_number(value):
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_status(value):
    if isinstance(value, bool):
        return "Above" if value else "Below"
    return str(value)


def normalize_reasons(value):
    if not value:
        return []
    if isinstance(value, str):
        return [line.strip(" -") for line in value.splitlines() if line.strip(" -")]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def build_message(ticker, signal, price=None, filtered=False, context=None):
    context = context or {}
    portfolio = load_portfolio()
    ticker = ticker.upper()
    position = portfolio.get(ticker)

    score, score_reasons = score_alert(ticker, signal, price)
    supplied_reasons = normalize_reasons(
        first_available(context, "reasons", "reason", "explanation")
    )
    reasons = list(dict.fromkeys(score_reasons + supplied_reasons))

    timeframe = first_available(context, "timeframe", "interval")
    rsi = first_available(context, "rsi", "rsi_value")
    rsi_ma = first_available(context, "rsi_ma", "rsiMA", "rsi_ma_value")
    ema21_status = first_available(
        context,
        "ema21_status",
        "ema21Status",
        "price_vs_ema21",
    )
    trend = first_available(context, "trend", "rsi_trend")
    structure = first_available(
        context,
        "hh_hl",
        "hhhl",
        "structure",
        "price_structure",
    )
    qqq_market = first_available(
        context,
        "qqq_market",
        "qqq_market_health",
        "market_health",
    )

    lines = ["🚨 Trading Dashboard Alert", ""]
    lines.append(f"Ticker: {ticker}")
    if timeframe is not None:
        lines.append(f"Timeframe: {timeframe}")
    if price is not None and price != "":
        lines.append(f"Price: {format_number(price)}")

    lines.extend(["", "Signal:", f"✅ {signal}"])

    if rsi is not None or rsi_ma is not None:
        lines.append("")
        if rsi is not None:
            lines.append(f"RSI: {format_number(rsi)}")
        if rsi_ma is not None:
            lines.append(f"RSI MA: {format_number(rsi_ma)}")

    technical_lines = []
    if ema21_status is not None:
        technical_lines.append(f"EMA21: {format_status(ema21_status)}")
    if trend is not None:
        technical_lines.append(f"Trend: {trend}")
    if structure is not None:
        technical_lines.append(f"HH/HL: {structure}")
    if technical_lines:
        lines.extend([""] + technical_lines)

    lines.extend(["", f"Score: {score}/10"])

    if qqq_market is not None:
        lines.extend(["", "QQQ Market:", str(qqq_market)])

    if reasons:
        lines.extend(["", "Reason:"])
        lines.extend(f"- {reason}" for reason in reasons)

    if position:
        shares = position["shares"]
        avg_cost = position["avg_cost"]
        ptype = position.get("type", "unknown")

        lines.extend([
            "",
            f"Position: {shares} shares",
            f"Avg cost: {format_number(avg_cost)}",
            f"Type: {ptype}",
        ])
    else:
        lines.extend(["", "Position: Not currently held / watchlist only."])

    return "\n".join(lines), score


@app.get("/")
def home():
    return {"status": "server running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("Incoming data:", data)

    ticker = data.get("ticker", "UNKNOWN")
    signal = data.get("signal", data.get("message", "No signal provided"))
    price = data.get("price")

    raw_message, score = build_message(
        ticker,
        signal,
        price,
        filtered=False,
        context=data,
    )

    filtered_sent = False
    background_tasks.add_task(send_telegram, raw_message, RAW_CHAT_ID)

    if score >= FILTER_SCORE_MIN:
        filtered_message, _ = build_message(
            ticker,
            signal,
            price,
            filtered=True,
            context=data,
        )
        background_tasks.add_task(
            send_telegram,
            filtered_message,
            FILTERED_CHAT_ID,
        )
        filtered_sent = True
    else:
        print(f"Filtered alert skipped. Score {score} is below minimum {FILTER_SCORE_MIN}")

    return {
        "status": "received",
        "delivery": "queued",
        "ticker": ticker,
        "score": score,
        "filtered_sent": filtered_sent,
        "raw_chat_id": RAW_CHAT_ID,
        "filtered_chat_id": FILTERED_CHAT_ID
    }
