"""
Lightweight Flask server to receive Slack Events API payloads.
Run alongside main.py:  python3 slack_bot/event_server.py
"""
import json
from pathlib import Path

from flask import Flask, request, jsonify
from slack_sdk import WebClient

from slack_bot.events import handle_member_joined, handle_dm_reply
from bot_setup.config import load_json, save_json

PRIVATE_POOLS_FILE = Path("private_pools.json")
app = Flask(__name__)


def _load_pools():
    if PRIVATE_POOLS_FILE.exists():
        return json.loads(PRIVATE_POOLS_FILE.read_text())
    return {}


def _save_pools(pools):
    PRIVATE_POOLS_FILE.write_text(json.dumps(pools, indent=2))


def _get_client():
    config = load_json("config.json")
    token = config.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not set in config.json")
    return WebClient(token=token)


@app.route("/slack/events", methods=["POST"])
def slack_events():
    payload = request.json

    # Slack URL verification handshake
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload["challenge"]})

    event = payload.get("event", {})
    event_type = event.get("type")
    pools = _load_pools()

    try:
        client = _get_client()
    except ValueError as e:
        print(f"[WARN] {e}")
        return jsonify({"ok": False}), 500

    if event_type == "member_joined_channel":
        handle_member_joined(event, client, pools, _save_pools)

    elif event_type == "message" and event.get("channel_type") == "im":
        handle_dm_reply(event, client, pools, _save_pools)

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(port=3000, debug=False)