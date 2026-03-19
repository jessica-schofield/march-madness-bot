#!/usr/bin/env python3
"""
Test harness for Slack setup and top N prompts
in March Madness Bot (mock mode).
"""

import json
from slack_sdk import WebClient
import slack_setup

# Use your existing config
CONFIG_FILE = "config.json"
cfg = json.load(open(CONFIG_FILE))
manager_id = cfg.get("SLACK_MANAGER_ID", "U12345678")  # fallback for testing

# Use a simulated client
client = WebClient(token="SIMULATE_TOKEN")

print("\n=== TEST: Cheeky intro ===")
intro_msg = slack_setup.cheeky_intro(manager_id)
print(intro_msg)

print("\n=== TEST: Prompt manager for top 3 (mock) ===")
# This will simulate asking for top N and returning a fake reply
def mock_wait_for_reply(client, user_id, prompt_text):
    print(f"[MOCK] DM to {user_id}: {prompt_text}")
    return "Alice (100)\nBob (95)\nCharlie (90)"  # fake top 3 reply

# Patch the wait_for_reply function in slack_setup
slack_setup.wait_for_reply = mock_wait_for_reply

top3 = slack_setup.prompt_manager_for_top("Main CBS Pool", "men", 3)
print("Parsed top 3:", top3)

print("\n=== TEST: Build daily summary blocks ===")
men_games = [
    {"home":"Duke","home_score":70,"home_seed":2,
     "away":"UNC","away_score":75,"away_seed":1,"gender":"men","id":"g1","date":"2026-03-18"}
]
women_games = [
    {"home":"Stanford","home_score":60,"home_seed":1,
     "away":"UCLA","away_score":65,"away_seed":3,"gender":"women","id":"g2","date":"2026-03-18"}
]

blocks = slack_setup.build_daily_summary_blocks(men_games, women_games, top3, top3)
print("Blocks ready to post:")
for b in blocks:
    print(b)