# filepath: /Users/jess/march-madness-bot/bot_setup/config.py

import json
from pathlib import Path

CONFIG_FILE = Path("config.json")

def load_json(filepath, default=None):
    if not filepath.exists():
        return default
    with open(filepath, 'r') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def get_default_config():
    return {
        "TOP_N": 5,
        "MINUTES_BETWEEN_MESSAGES": 60,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "TOURNAMENT_END_MEN": "2026-04-07",
        "TOURNAMENT_END_WOMEN": "2026-04-06",
        "POOLS": [{"SOURCE": "custom"}],
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json"
    }