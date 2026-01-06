import os
from flask import Flask, request,Response, jsonify
import requests
import xmltodict
import copy
from datetime import datetime
import random
from flask_cors import CORS
import slack


app = Flask(__name__)
CORS(app)


# =========================
# 5. API: Status options endpoint
# =========================
# @app.route('/status-options', methods=['GET'])
# def get_status_options():
#     return jsonify({"options": ORDER_STATUS_LIST[1:]})


@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(force=True)

    # 🔑 Slack URL verification
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        return Response(challenge, status=200, mimetype="text/plain")

    return slack.handle_event(request.json)

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "OMS by Slack is running 🚀", 200

# def main():
#     port = int(os.environ.get("PORT", 10000))
#     app.run(host="0.0.0.0", port=port)
