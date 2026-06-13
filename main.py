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

from fastapi import FastAPI, Request
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


def build_message(ticker, signal, price=None, filtered=False):
    portfolio = load_portfolio()
    ticker = ticker.upper()
    position = portfolio.get(ticker)

    score, reasons = score_alert(ticker, signal, price)

    header = "⭐ FILTERED ALERT" if filtered else "🚨 RAW ALERT"

    msg = f"{header}\n"
    msg += f"Ticker: {ticker}\n"
    msg += f"Signal: {signal}\n"

    if price:
        msg += f"Price: {price}\n"

    msg += f"Score: {score}/10\n"

    if reasons:
        msg += "\nReasons:\n"
        for r in reasons:
            msg += f"✅ {r}\n"

    if position:
        shares = position["shares"]
        avg_cost = position["avg_cost"]
        ptype = position.get("type", "unknown")

        msg += f"\nPosition: {shares} shares\n"
        msg += f"Avg cost: {avg_cost}\n"
        msg += f"Type: {ptype}\n"

        if ptype == "high_beta":
            msg += "\nNote: High beta stock. Avoid chasing; add only on confirmation or pullback."
        elif ptype == "core":
            msg += "\nNote: Core position. Focus on trend, not small intraday noise."
    else:
        msg += "\nPosition: Not currently held / watchlist only."

    return msg, score


@app.get("/")
def home():
    return {"status": "server running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("Incoming data:", data)

    ticker = data.get("ticker", "UNKNOWN")
    signal = data.get("signal", data.get("message", "No signal provided"))
    price = data.get("price")

    raw_message, score = build_message(ticker, signal, price, filtered=False)

    raw_ok = send_telegram(raw_message, RAW_CHAT_ID)


    filtered_sent = False
    filtered_ok = False

    if score >= FILTER_SCORE_MIN:
        filtered_message, _ = build_message(ticker, signal, price, filtered=True)
        filtered_ok = send_telegram(filtered_message, FILTERED_CHAT_ID)
        filtered_sent = True
    else:
        print(f"Filtered alert skipped. Score {score} is below minimum {FILTER_SCORE_MIN}")

    return {
        "status": "received",
        "ticker": ticker,
        "score": score,
        "raw_ok": raw_ok,
        "filtered_ok": filtered_ok,
        "filtered_sent": filtered_sent,
        "filtered_ok": filtered_ok,
        "raw_chat_id": RAW_CHAT_ID,
        "filtered_chat_id": FILTERED_CHAT_ID
    }
