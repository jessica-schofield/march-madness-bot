#!/usr/bin/env python3
"""
slack_setup.py

Interactive Slack setup & DM-driven or CLI-driven leaderboard prompting
for March Madness Bot.
"""

import json
import time
import random
import datetime
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

CONFIG_FILE = Path("config.json")

# ------------------------------
# Slack Simulator / CLI preview
# ------------------------------
def simulate_slack_message(blocks):
    """Pretty-print Slack message blocks in the terminal."""
    for block in blocks:
        t = block.get("type")
        content = block.get("text", {}).get("text", "")
        if t == "section":
            print(content)
        elif t == "divider":
            print("-" * 50)
    print("\n" + "="*50 + "\n")

# ------------------------------
# Slack / CLI helpers
# ------------------------------
def send_dm(client: WebClient, user_id, text, blocks=None, mock=True):
    if mock:
        print(f"[MOCK] DM to {user_id}: {text}")
        if blocks: simulate_slack_message(blocks)
        return

    try:
        response = client.conversations_open(users=user_id)
        channel_id = response["channel"]["id"]
        client.chat_postMessage(channel=channel_id, text=text, blocks=blocks)
    except SlackApiError as e:
        print(f"[ERROR] Failed to send DM: {e.response['error']}")

def wait_for_reply(client: WebClient, user_id, prompt_text, mock=True):
    """Send DM, then wait for reply (mock or Slack)."""
    if mock:
        print(f"[MOCK PROMPT] {prompt_text}")
        # Allow user to type manually in CLI
        reply = input("Enter mock reply (one line per player, e.g., Alice (100)):\n")
        return reply.strip() or "\n".join([f"Alice (100)", f"Bob (95)", f"Charlie (90)"])
    
    send_dm(client, user_id, prompt_text, mock=mock)
    print(f"[INFO] Waiting for Slack reply from {user_id}...")
    while True:
        try:
            history = client.conversations_history(channel=user_id, limit=1)
            messages = history.get("messages", [])
            if messages:
                reply = messages[0]["text"].strip()
                if reply:
                    return reply
        except SlackApiError:
            pass
        time.sleep(3)

# ------------------------------
# Cheeky intro
# ------------------------------
def cheeky_intro(user_id):
    intros = [
        f"Yo {user_id}! Let's get this bot ready to wreak havoc on brackets 😎",
        f"Hey there! Time to configure your March Madness chaos coordinator 🏀",
        f"Alright boss, let's make me smart enough to annoy the right people 😂"
    ]
    return random.choice(intros)

# ------------------------------
# Prompt manager for top N
# ------------------------------
def prompt_manager_for_top(pool_name, gender, n, mock=True):
    """Ask manager via DM or CLI for missing top N players"""
    # Load Slack ID if present
    manager_id = None
    if CONFIG_FILE.exists():
        cfg = json.load(CONFIG_FILE.open())
        manager_id = cfg.get("SLACK_MANAGER_ID")

    client = WebClient(token="SIMULATE_TOKEN")  # In real mode, use actual bot token

    msg = f"⚠️ CBS leaderboard scraping failed for *{pool_name}* ({gender}).\n" \
          f"Please reply with top {n} in the format:\n" \
          "Player1 (score)\nPlayer2 (score)\nPlayer3 (score)"

    reply = ""
    if mock or not manager_id:
        # CLI input mode
        print(f"\n[CLI PROMPT] {msg}")
        lines = []
        for i in range(n):
            line = input(f"Enter player {i+1}: ").strip()
            if not line:
                line = f"TestUser{i+1} ({100-i})"
            lines.append(line)
        reply = "\n".join(lines)
    else:
        # Slack DM mode
        reply = wait_for_reply(client, manager_id, msg, mock=mock)

    # Parse reply
    top_list = []
    for line in reply.splitlines():
        line = line.strip()
        if line:
            top_list.append(line)
            if len(top_list) == n:
                break
    return top_list

# ------------------------------
# Build Slack / CLI message for individual game
# ------------------------------
def build_slack_message(game, top_men, top_women):
    home_score = int(game['home_score'])
    away_score = int(game['away_score'])
    home_seed = game.get('home_seed', 0)
    away_seed = game.get('away_seed', 0)
    upset = "⚡🔥" if (home_score>away_score and home_seed>away_seed) or \
                       (away_score>home_score and away_seed>home_seed) else ""
    bracket_emoji = "🏆" if game['gender']=='men' else "👑"

    men_text = "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(top_men))
    women_text = "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(top_women))

    blocks = [
        {"type":"section","text":{"type":"mrkdwn",
          "text":f"{bracket_emoji} {upset} *FINAL*: {game['away']} {away_score} - {home_score} {game['home']} {upset}"}},
        {"type":"divider"},
        {"type":"section","text":{"type":"mrkdwn",
          "text":f"*Men’s Top {len(top_men)}:* \n{men_text}"}},
        {"type":"divider"},
        {"type":"section","text":{"type":"mrkdwn",
          "text":f"*Women’s Top {len(top_women)}:* \n{women_text}"}}
    ]
    return blocks

# ------------------------------
# Build daily summary blocks
# ------------------------------
def build_daily_summary_blocks(men_games, women_games, top_men, top_women):
    today = datetime.date.today()

    def game_text_with_upset(games):
        lines = []
        for g in games:
            home_score = int(g['home_score'])
            away_score = int(g['away_score'])
            home_seed = g.get('home_seed',0)
            away_seed = g.get('away_seed',0)
            upset = " ⚡🔥" if (home_score>away_score and home_seed>away_seed) or \
                               (away_score>home_score and away_seed>home_seed) else ""
            lines.append(f"- {g['away']} {g['away_score']} - {home_score} {g['home']}{upset}")
        return "\n".join(lines) if lines else "No games yesterday. 😴"

    def make_funny_rankings(top_list):
        return [f"{i+1}. {entry}" for i, entry in enumerate(top_list)]

    intros = [
        "☀️ Good morning! Here’s the madness from yesterday:",
        "🎉 Daily chaos report incoming!",
        "😂 Buckle up: yesterday in March Madness...",
        "☕ Grab your coffee, here’s what happened on the court yesterday:",
        "🏀 Another day, another bracket disaster report:"
    ]
    intro = random.choice(intros)

    men_top_text = "\n".join(make_funny_rankings(top_men))
    women_top_text = "\n".join(make_funny_rankings(top_women))

    blocks = [{"type":"section","text":{"type":"mrkdwn","text":intro}}]
    blocks.append({"type":"section","text":{"type":"mrkdwn","text":f"*🏀 Men’s Games:* \n{game_text_with_upset(men_games)}"}})
    blocks.append({"type":"divider"})
    blocks.append({"type":"section","text":{"type":"mrkdwn","text":f"*👑 Women’s Games:* \n{game_text_with_upset(women_games)}"}})
    blocks.append({"type":"divider"})
    blocks.append({"type":"section","text":{"type":"mrkdwn","text":f"*📊 Men’s Top {len(top_men)}:* \n{men_top_text}"}})
    blocks.append({"type":"divider"})
    blocks.append({"type":"section","text":{"type":"mrkdwn","text":f"*👩‍🦰 Women’s Top {len(top_women)}:* \n{women_top_text}"}})

    return blocks

# ------------------------------
# Run interactive setup (Slack DM or CLI)
# ------------------------------
def run_setup(client=None, manager_id=None, mock=True):
    """Launch interactive setup to fill missing config"""
    cfg = {}
    if CONFIG_FILE.exists():
        cfg = json.load(CONFIG_FILE.open())

    if not manager_id and not mock:
        raise ValueError("manager_id required for Slack DM setup")

    if not cfg.get("SLACK_MANAGER_ID"):
        cfg["SLACK_MANAGER_ID"] = manager_id
        send_dm(client, manager_id, cheeky_intro(manager_id), mock=mock)

    # Future steps (POOLS, WEBHOOK, etc.) can be added here
    with CONFIG_FILE.open("w") as f:
        json.dump(cfg, f, indent=2)
    send_dm(client, manager_id or "CLI", "🎉 Config saved! Ready to post madness 😈🏀", mock=mock)