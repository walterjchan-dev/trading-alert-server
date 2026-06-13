from fastapi import FastAPI, Request
import requests
import json

app = FastAPI()

TELEGRAM_BOT_TOKEN = "8139067560:AAHcW5k5EsBjPKsrnuaCg9QysO9HtBdIqoc"
TELEGRAM_CHAT_ID = "8435430741"

def load_portfolio():
    with open("portfolio.json", "r") as f:
        return json.load(f)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    })

def build_message(ticker, signal, price=None):
    portfolio = load_portfolio()
    position = portfolio.get(ticker.upper())

    msg = f"🚨 {ticker.upper()} Alert\n"
    msg += f"Signal: {signal}\n"

    if price:
        msg += f"Price: {price}\n"

    if position:
        shares = position["shares"]
        avg_cost = position["avg_cost"]
        ptype = position.get("type", "unknown")

        msg += f"\nPosition: {shares} shares\n"
        msg += f"Avg cost: {avg_cost}\n"
        msg += f"Type: {ptype}\n"

        if ptype == "high_beta":
            msg += "\nNote: High beta stock. Avoid chasing; consider trim on spike or add only on pullback."
        elif ptype == "core":
            msg += "\nNote: Core position. Focus on trend, not small intraday noise."
    else:
        msg += "\nPosition: Not currently held / watchlist only."

    return msg

@app.get("/")
def home():
    return {"status": "server running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    ticker = data.get("ticker", "UNKNOWN")
    signal = data.get("signal", data.get("message", "No signal provided"))
    price = data.get("price")

    message = build_message(ticker, signal, price)
    send_telegram(message)

    return {"status": "sent", "message": message}
