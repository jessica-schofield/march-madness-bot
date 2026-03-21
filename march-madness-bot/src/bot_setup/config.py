# This file handles configuration loading and saving, including managing JSON files for bot settings.

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / 'config.json'
SEEN_FILE = Path(__file__).parent / 'seen_games.json'
LAST_POST_FILE = Path(__file__).parent / 'last_post.json'
YEARLY_FLAG_FILE = Path(__file__).parent / 'yearly_reminder_flag.json'


def load_json(file_path, default=None):
    if file_path.exists():
        with open(file_path, 'r') as f:
            return json.load(f)
    return default


def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)


def needs_setup(config):
    return not config.get("SLACK_WEBHOOK_URL") or not config.get("SLACK_MANAGER_ID")