import datetime
import json
from pathlib import Path
from slack_sdk import WebClient
from yearly_setup_reminder import yearly_reminder, next_business_day
from config import YEARLY_REMINDER_FLAG_FILE

CONFIG_FILE = Path("config.json")
YEARLY_FLAG_FILE = YEARLY_REMINDER_FLAG_FILE

def load_config():
    return json.load(CONFIG_FILE.open())

def save_flag(flag):
    with YEARLY_FLAG_FILE.open("w") as f:
        json.dump(flag, f, indent=2)

def load_flag():
    if YEARLY_FLAG_FILE.exists():
        return json.load(YEARLY_FLAG_FILE.open())
    return {"stop": False, "last_reminder": None}

def main():
    cfg = load_config()
    manager_id = cfg.get("SLACK_MANAGER_ID")
    if not manager_id:
        print("⚠️ SLACK_MANAGER_ID not set in config.json. Cannot send yearly setup reminder.")
        return

    client = WebClient(token=cfg.get("SLACK_BOT_TOKEN"))

    today = datetime.date.today()
    flag = load_flag()

    # Check if reminder is scheduled for today
    reminder_due = False
    if flag.get("last_reminder"):
        next_reminder = datetime.date.fromisoformat(flag["last_reminder"])
        if today >= next_reminder:
            reminder_due = True

    # Otherwise check if today is March 10 (or next business day if weekend)
    march10 = datetime.date(today.year, 3, 10)
    march10 = next_business_day(march10)
    if today == march10:
        reminder_due = True

    if reminder_due and not flag.get("stop"):
        yearly_reminder(client, manager_id)
    else:
        print(f"✅ No reminder due today ({today}). Next scheduled check continues.")

if __name__ == "__main__":
    main()