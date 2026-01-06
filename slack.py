from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import os
import re
import requests
import json

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_SIGNING_SECRET")
# Slack app
app = App(token=SLACK_BOT_TOKEN)

FLASK_CHAT_URL = "http://localhost:5000/chat"   # your Flask chatbot API


# -------------------------
# When someone mentions bot
# -------------------------
@app.event("app_mention")
def mention_handler(event, say):
    user = event.get("user")
    say(f"Hi <@{user}> 👋 I’m ready! Type *create order* to start.")


# -------------------------
# Message Handler → sends text to Flask chatbot
# -------------------------
@app.message(re.compile(".*"))
def handle_message(message, say):
    user = message["user"]
    text = message.get("text", "")

    # Send to your Flask chatbot
    payload = {"message": text}
    try:
        resp = requests.post(FLASK_CHAT_URL, json=payload)
        result = resp.json()

        # Format reply
        reply = result.get("reply")

        # If reply is list (logs)
        if isinstance(reply, list):
            msg = "\n".join([str(x) for x in reply])
        else:
            msg = reply

        say(f"<@{user}> 👉\n{msg}")

    except Exception as e:
        say(f"⚠️ Error contacting OMS server: {e}")

# -------------------------
# ✅ REQUIRED FOR main.py
# -------------------------
def main():
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

# Run Socket Mode
if __name__ == "__main__":
    main()
