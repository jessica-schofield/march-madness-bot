"""
CLI interaction helpers for March Madness Bot setup.
Pure input/output utilities — no Playwright, CBS, or Slack DM dependencies.
"""
import sys
from pathlib import Path

from bot_setup.config import CONFIG_FILE, save_json

SLACK_WEBHOOK_HELP = """
📋 HOW TO GET YOUR SLACK WEBHOOK URL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Go to https://api.slack.com/apps and click "Create New App"
2. Choose "From scratch", give it a name (e.g. "March Madness Bot"), pick your workspace
3. In the left sidebar click "Incoming Webhooks"
4. Toggle "Activate Incoming Webhooks" to ON
5. Click "Add New Webhook to Workspace" at the bottom
6. Choose the Slack channel you want the bot to post in, click "Allow"
7. Copy the Webhook URL — it looks like:
   https://hooks.slack.com/services/YOUR/WEBHOOK/URL
8. Paste it here when prompted

⚠️  Keep this URL private — anyone with it can post to your Slack!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

SLACK_MANAGER_HELP = """
📋 HOW TO FIND YOUR SLACK USER ID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your Slack User ID is used so the bot can tag you in yearly reminders.

In Slack desktop app:
1. Click your avatar / profile picture in the bottom left corner
2. Click "Profile"
3. Click the "⋮" (three dots) button in your profile panel
4. Click "Copy member ID"
5. It looks like: U0123456789
6. Paste it here when prompted

In Slack browser:
1. Click your avatar in the top right corner
2. Click "Profile"
3. Click the "⋮" (three dots) button in your profile panel
4. Click "Copy member ID"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

SLACK_BOT_TOKEN_HELP = """
📋 HOW TO GET YOUR SLACK BOT TOKEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Go to https://api.slack.com/apps and open your March Madness Bot app
   (or create one if you haven't yet — see webhook setup for instructions)
2. In the left sidebar click "OAuth & Permissions"
3. Under "Bot Token Scopes" make sure these are added:
   • chat:write
   • im:write
   • im:history
   • users:read
4. Click "Install App to Workspace" (or "Reinstall" if already installed)
5. Copy the "Bot User OAuth Token" — it starts with xoxb-
6. Paste it here when prompted

⚠️  Keep this token private — anyone with it can post as your bot!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

TOURNAMENT_DATES_HELP = """
📋 TOURNAMENT END DATES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The men's and women's championships typically fall on different days.

To find the dates:
  • Google "NCAA tournament schedule {year}"
  • Men's final is usually the first Monday in April
  • Women's final is usually the Sunday before

Enter dates in YYYY-MM-DD format, e.g. 2026-04-06
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

POOL_URL_HELP = """
📋 BRACKET POOL URLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Supported sites:

🏀 CBS Sports
   Go to your group's standings page — URL looks like:
   https://www.cbssports.com/collegebasketball/brackets/groups/XXXXXX/standings

🏀 ESPN Tournament Challenge
   Go to your group page — URL looks like:
   https://fantasy.espn.com/tournament-challenge-bracket/2026/en/group?groupID=XXXXXX

🏀 Yahoo Tourney Pick'em
   Go to your group's standings page — URL looks like:
   https://tournament.fantasysports.yahoo.com/t1/group/XXXXXX/standings

You can mix and match — e.g. men's on CBS and women's on ESPN.
Leave blank if you only have one pool.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def get_input_safe(prompt, default=None, config=None):
    """Prompt for input, save and exit cleanly if user types 'exit'."""
    try:
        value = input(f"{prompt}{' [Default: ' + str(default) + ']' if default is not None else ''}: ").strip()
    except EOFError:
        # Running non-interactively (e.g. cron) — return default silently
        if default is not None:
            return str(default)
        return ""
    if value.lower() == "exit":
        print("[INFO] Exiting setup. Saving current configuration...")
        if config is not None:
            save_json(CONFIG_FILE, config)
        sys.exit(0)
    return value if value else (str(default) if default is not None else "")


def ask_if_missing(config, key, prompt, default, cast=str):
    """Only ask for a config value if it isn't already set."""
    if key in config and config[key] not in (None, ""):
        return config[key]
    value = get_input_safe(prompt, default=default, config=config)
    try:
        config[key] = cast(value)
    except Exception:
        config[key] = value
    return config[key]


def ask_with_help(prompt, help_text, default="", config=None):
    """Ask a CLI question with optional inline help text."""
    print(f"\n{prompt}")
    choice = get_input_safe(
        "Type your answer, 'help' for instructions, or leave blank to skip",
        default=default if default else None,
        config=config
    )
    if choice.lower() == "help":
        print(help_text)
        choice = get_input_safe(
            "Now enter your value, or leave blank to skip",
            default=default if default else None,
            config=config
        )
    return choice


def get_missing_config_fields(config):
    """Return a list of (key, label) tuples for any important empty config fields."""
    missing = []
    if not config.get("SLACK_WEBHOOK_URL"):
        missing.append(("SLACK_WEBHOOK_URL", "Slack Webhook URL"))
    if not config.get("SLACK_MANAGER_ID"):
        missing.append(("SLACK_MANAGER_ID", "Slack Manager User ID"))
    return missing


def ask_slack_credentials_cli(config):
    """Collect webhook URL, bot token, and manager user ID via CLI prompts."""
    from dotenv import load_dotenv, set_key
    import os
    load_dotenv()

    print("\n--- Slack Setup ---")

    webhook = ask_with_help(
        "Slack webhook URL",
        SLACK_WEBHOOK_HELP,
        default=config.get("SLACK_WEBHOOK_URL", ""),
        config=config,
    )
    # Only overwrite if user provided a non-empty value OR there was no existing value
    if webhook or not config.get("SLACK_WEBHOOK_URL"):
        config["SLACK_WEBHOOK_URL"] = webhook

    if not webhook:
        print("[WARN] No webhook URL set — bot will run in mock mode.")

    existing_token = os.environ.get("SLACK_BOT_TOKEN", "")
    token = ask_with_help(
        "🤖 Slack Bot Token — needed to send DMs and reminders. Starts with xoxb-",
        SLACK_BOT_TOKEN_HELP,
        default="(already set)" if existing_token else "",
        config=config
    )
    if token and token != "(already set)":
        env_path = Path(".env")
        if not env_path.exists():
            env_path.write_text("")
        set_key(str(env_path), "SLACK_BOT_TOKEN", token)
        os.environ["SLACK_BOT_TOKEN"] = token
        print("[INFO] Bot token saved to .env")
    elif existing_token:
        print("[INFO] Using existing bot token from .env")
    else:
        print("[WARN] No bot token set — Slack DMs and reminders won't work.")

    manager_id = ask_with_help(
        "Slack Manager User ID",
        SLACK_MANAGER_HELP,
        default=config.get("SLACK_MANAGER_ID", ""),
        config=config,
    )
    if manager_id or not config.get("SLACK_MANAGER_ID"):
        config["SLACK_MANAGER_ID"] = manager_id

    return config
