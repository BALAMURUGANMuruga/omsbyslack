import os
import requests

from chat_logic import chat_logic


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
     # URL verification
    if data.get("type") == "url_verification":
        return data.get("challenge")

    event = data.get("event", {})
    event_type = event.get("type")

    if event_type == "app_mention" or (
        event_type == "message" and not event.get("bot_id")
    ):
        channel = event.get("channel")
        user = event.get("user")
        text = event.get("text", "")

        # remove bot mention if present
        clean_text = text.split(">")[-1].strip()

        reply = chat_logic(clean_text, user_id=user)
        send_message(channel, reply)

    return "ok"
