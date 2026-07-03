from fastapi import FastAPI, Request, HTTPException
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN not set in environment")

# Import helper functions and configuration from main.py
# main.py defines find_value_bets, MIN_CONFIDENCE, MAX_CONFIDENCE, MIN_ODDS, MAX_ODDS
from main import find_value_bets, MIN_CONFIDENCE, MAX_CONFIDENCE, MIN_ODDS, MAX_ODDS

app = FastAPI()

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        # log but don't crash
        print(f"send_message error: {e}")
        return None


@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    # security check: path token must match env token
    if token != TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    update = await request.json()

    # Extract message (normal or edited)
    message = update.get("message") or update.get("edited_message") or update.get("callback_query")
    if not message:
        return {"ok": True, "info": "no message"}

    # Handle callback_query
    if update.get("callback_query"):
        # simple ack
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        send_message(chat_id, "Callback received")
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()

    if not text:
        return {"ok": True}

    # Command handling
    if text.startswith("/start"):
        reply = (
            f"🎯 *Betting AI Bot - Safe Value Betting*\n\n"
            f"Καλώς ήρθες! Αυτό το bot βρίσκει *value bets* με:\n"
            f"- ✅ Confidence Range: *{MIN_CONFIDENCE}% - {MAX_CONFIDENCE}%*\n"
            f"- ✅ Odds Range: *{MIN_ODDS} - {MAX_ODDS}*\n\n"
            f"Στείλε /topbets για να δεις προτάσεις."
        )
        send_message(chat_id, reply)
        return {"ok": True}

    if text.startswith("/status"):
        reply = (
            f"✅ *Bot Status*\n\n"
            f"🟢 Online\n"
            f"🎯 Confidence Range: {MIN_CONFIDENCE}% - {MAX_CONFIDENCE}%\n"
            f"💰 Odds Range: {MIN_ODDS} - {MAX_ODDS}\n"
            f"Ενημέρωση: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_message(chat_id, reply)
        return {"ok": True}

    if text.startswith("/help"):
        reply = (
            "📋 *Available Commands:*\n"
            "/start - Ενεργοποίηση bot\n"
            "/status - Κατάσταση bot\n"
            "/topbets - Top value bets\n"
            "/help - Βοήθεια\n"
        )
        send_message(chat_id, reply)
        return {"ok": True}

    if text.startswith("/topbets"):
        bets = find_value_bets()
        if not bets:
            reply = (
                f"❌ Δεν υπάρχουν live value bets αυτή τη στιγμή με {MIN_CONFIDENCE}%-{MAX_CONFIDENCE}% confidence "
                f"και odds {MIN_ODDS}-{MAX_ODDS}.\n\n"
                "ℹ️ Σημείωση: χρειάζονται αγώνες σε εξέλιξη και διαθέσιμα odds από τον bookmaker τη δεδομένη στιγμή."
            )
            send_message(chat_id, reply)
            return {"ok": True}

        text_reply = "🎯 *Top Value Bets - Sorted by ROI*\n\n"
        for i, bet in enumerate(bets, 1):
            text_reply += (
                f"{i}. *{bet['match']}*\n"
                f"Pick: {bet['pick']}\n"
                f"Odds: {bet['odds']}\n"
                f"Confidence: {bet['confidence']}% {bet['risk_level']}\n"
                f"ROI: +{bet['roi']}%\n\n"
            )
        send_message(chat_id, text_reply)
        return {"ok": True}

    # default echo for unknown messages
    if text.startswith("/"):
        send_message(chat_id, "Άγνωστη εντολή. Στείλε /help για διαθέσιμες εντολές.")
    else:
        # Ignore other chat messages
        pass

    return {"ok": True}
