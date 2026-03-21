#!/usr/bin/env python3
"""
setup.py

Interactive setup for March Madness Bot:
- Command line setup
- Slack DM setup
"""

import json
from pathlib import Path
import slack_setup

CONFIG_FILE = Path("config.json")


def get_input(prompt, default=None, required=False):
    while True:
        val = input(f"{prompt} " + (f"[Default: {default}]: " if default else ": "))
        if not val and default is not None:
            return default
        if val:
            return val
        if required:
            print("This field is required. Please enter a value.")


def command_line_setup():
    print("\n=== COMMAND LINE SETUP ===")
    config = {}
    config["SLACK_WEBHOOK_URL"] = get_input("Enter Slack Webhook URL (can leave blank for MOCK mode)", default="")
    config["SLACK_MANAGER_ID"] = get_input("Enter your Slack ID (optional, for DM fallback)", default="")
    config["MOCK_SLACK"] = True if not config["SLACK_WEBHOOK_URL"] else False
    config["TOP_N"] = int(get_input("How many top users to track?", default="3"))
    config["MINUTES_BETWEEN_MESSAGES"] = int(get_input("Minutes between automated messages?", default="30"))

    # CBS Pool URLs
    men_url = get_input("CBS Men’s Pool URL (leave blank to skip)", default="")
    women_url = get_input("CBS Women’s Pool URL (leave blank to skip)", default="")
    config["POOLS"] = []
    if men_url or women_url:
        pool = {"NAME": "Main CBS Pool", "SOURCE": "cbs"}
        if men_url:
            pool["MEN_URL"] = men_url
        if women_url:
            pool["WOMEN_URL"] = women_url
        config["POOLS"].append(pool)

    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)
    print("\n✅ Configuration saved to config.json")
    print("You can now run `python3 main.py` to start the bot.\n")


def slack_dm_setup():
    print("\n=== SLACK DM SETUP ===")
    print("We'll need your Slack ID to DM you for setup instructions.")
    print("To find your Slack ID:")
    print("1. Open Slack in a browser.")
    print("2. Click your profile -> 'Copy member ID'.")
    print("3. Paste it below.\n")
    slack_id = get_input("Enter your Slack ID", required=True)

    # Save minimal config for DM setup
    config = {"SLACK_MANAGER_ID": slack_id, "MOCK_SLACK": True}
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)

    print("\nRunning Slack interactive setup (mock)...")
    client = None  # In real world: WebClient(token="YOUR_SLACK_BOT_TOKEN")
    slack_setup.run_setup(client, slack_id)
    print("\n✅ Slack setup complete. config.json updated.\n")


def main_setup():
    print("\nWelcome to March Madness Bot setup!\n")
    print("Do you want to set up the bot via Slack DMs or Command Line?")
    print("1) Command Line (recommended if Slack access is not ready)")
    print("2) Slack DM (requires Slack account and bot token)\n")

    choice = get_input("Enter 1 or 2", required=True)
    if choice == "1":
        command_line_setup()
    elif choice == "2":
        slack_dm_setup()
    else:
        print("Invalid choice. Please run setup again and enter 1 or 2.")


if __name__ == "__main__":
    main_setup()
