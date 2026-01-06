import os
import requests

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_API_URL = "https://slack.com/api/chat.postMessage"


def send_message(channel, text):
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "channel": channel,
        "text": text
    }
    requests.post(SLACK_API_URL, headers=headers, json=payload)


def handle_event(data):
    """
    Called from Flask route: /slack/events
    """

    # 1️⃣ Slack URL verification
    if data.get("type") == "url_verification":
        return data.get("challenge")

    # 2️⃣ Handle message events
    event = data.get("event", {})
    event_type = event.get("type")

    if event_type == "app_mention":
        channel = event.get("channel")
        send_message(channel, "👋 Hi! Type *create order* to begin.")
        return "ok"

    if event_type == "message" and not event.get("bot_id"):
        channel = event.get("channel")
        text = event.get("text", "").lower()

        if "create order" in text:
            send_message(channel, "✅ Order creation started")

    return "ok"
