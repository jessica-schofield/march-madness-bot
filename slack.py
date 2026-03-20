import os
import requests
import json
from pathlib import Path

# Load config
CONFIG_FILE = Path("config.json")
config = json.load(CONFIG_FILE.open())

WEBHOOK_URL = config.get("slack_webhook_url")
MOCK = config.get("mock_slack", True)

def post_message(text):
    if MOCK:
        print(f"[SLACK MOCK] {text}\n{'-'*50}")
    else:
        requests.post(WEBHOOK_URL, json={"text": text})