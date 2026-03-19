# yearly_setup_reminder.py
import json
import datetime
import subprocess
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time
import slack_setup  # interactive Slack setup

CONFIG_FILE = Path("config.json")
YEARLY_FLAG_FILE = Path("yearly_reminder_flag.json")  # Tracks last reminders/stop status

# ------------------------------
# Helpers
# ------------------------------
def load_config():
    return json.load(CONFIG_FILE.open())

def save_config(cfg):
    with CONFIG_FILE.open("w") as f:
        json.dump(cfg, f, indent=2)

def load_flag():
    if YEARLY_FLAG_FILE.exists():
        return json.load(YEARLY_FLAG_FILE.open())
    return {"stop": False, "last_reminder": None, "LIVE_FOR_YEAR": False}

def save_flag(flag):
    with YEARLY_FLAG_FILE.open("w") as f:
        json.dump(flag, f, indent=2)

def send_dm(client: WebClient, user_id, text, blocks=None):
    """Send a DM to Slack manager"""
    try:
        client.chat_postMessage(channel=user_id, text=text, blocks=blocks)
    except SlackApiError as e:
        print(f"[ERROR] Sending DM failed: {e.response['error']}")

def is_weekend(date):
    return date.weekday() >= 5  # 5=Saturday, 6=Sunday

def next_business_day(date):
    while is_weekend(date):
        date += datetime.timedelta(days=1)
    return date

def git_update():
    print("🔄 Pulling latest updates from git...")
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"[ERROR] Git update failed: {e}")

# ------------------------------
# Yearly reminder logic
# ------------------------------
def yearly_reminder(client: WebClient, manager_id):
    cfg = load_config()
    flag = load_flag()

    if flag.get("stop"):
        print("🛑 Manager has requested no more reminders this year.")
        return

    today = datetime.date.today()
    reminder_date = datetime.date(today.year, 3, 10)
    reminder_date = next_business_day(reminder_date)

    # Override if a "remind me later" is set
    if flag.get("last_reminder"):
        reminder_date = datetime.date.fromisoformat(flag["last_reminder"])

    # Fire if today >= scheduled date or live mode already enabled
    if today < reminder_date and not flag.get("LIVE_FOR_YEAR", False):
        print(f"⏱ Not time yet. Next reminder scheduled for {reminder_date}")
        return
    else:
        print(f"⚡ Reminder firing! Scheduled for {reminder_date}, today is {today}")

    # Send initial DM
    send_dm(client, manager_id,
        "🏀 Hey there! It's March Madness setup time for next year! 🎉\n"
        "Do you want to set up the bot for the new season? Reply with `YES`, `NO`, `REMIND ME LATER`, or `STOP`.")

    # Wait for reply (for now simulated with input; replace with Slack events in prod)
    start_time = time.time()
    reply = None
    while not reply and time.time() - start_time < 1800:  # 30 min timeout
        reply = input("Simulate manager reply (YES/NO/REMIND ME LATER/STOP): ").strip().upper()
        if reply:
            break

    # Timeout handling
    if not reply:
        send_dm(client, manager_id,
            "⌛ You didn't respond in 30 minutes. Should I remind you later? Reply `YES` or `NO`.")
        reply = input("Simulate reminder response: ").strip().upper()
        if reply == "YES":
            next_reminder = next_business_day(today + datetime.timedelta(days=3))
            flag["last_reminder"] = str(next_reminder)
            save_flag(flag)
            send_dm(client, manager_id, f"⏰ Got it! I'll remind you again on {next_reminder} 🗓️")
            return
        elif reply == "NO":
            flag["stop"] = True
            save_flag(flag)
            send_dm(client, manager_id, "❌ No worries! I won't bug you again this year.")
            return

    # Explicit STOP
    if reply == "STOP":
        flag["stop"] = True
        save_flag(flag)
        send_dm(client, manager_id, "🛑 All future reminders stopped. Peace out! ✌️")
        return

    # Explicit NO
    if reply == "NO":
        flag["stop"] = True
        save_flag(flag)
        send_dm(client, manager_id, "❌ Got it! I'll check in next year instead.")
        return

    # Explicit REMIND ME LATER
    if reply == "REMIND ME LATER":
        next_reminder = next_business_day(today + datetime.timedelta(days=3))
        flag["last_reminder"] = str(next_reminder)
        save_flag(flag)
        send_dm(client, manager_id, f"⏰ Sure! I'll remind you again on {next_reminder} 🗓️")
        return

    # Explicit YES
    if reply == "YES":
        send_dm(client, manager_id, "🎯 Awesome! Pulling latest bot updates and launching DM setup... 🔄")
        git_update()

        # Clear everything except essential info
        cfg = load_config()
        new_cfg = {
            "PLAYWRIGHT_HEADLESS": cfg.get("PLAYWRIGHT_HEADLESS", True),
            "SLACK_MANAGER_ID": manager_id
        }
        save_config(new_cfg)

        # Launch interactive Slack DM setup
        slack_setup.run_setup(client, manager_id)
        send_dm(client, manager_id, "🎉 All done! Ready for next season 🏀👑")

    # --- Ask about live mode at the end ---
    reply_live = input("⚡ Are we live yet? (YES/NO): ").strip().upper()
    flag["LIVE_FOR_YEAR"] = reply_live == "YES"
    save_flag(flag)
    if flag["LIVE_FOR_YEAR"]:
        send_dm(client, manager_id, "🚀 The bot is now live for this year’s tournaments!")
    else:
        send_dm(client, manager_id,
                "⏳ Bot will remain in TEST MODE until the tournaments start. All messages will be mock outputs.")

    # Reset yearly flag for next year (keeping LIVE_FOR_YEAR=False)
    next_year_reminder = datetime.date(today.year + 1, 3, 10)
    flag.update({"stop": False, "last_reminder": str(next_year_reminder)})
    save_flag(flag)