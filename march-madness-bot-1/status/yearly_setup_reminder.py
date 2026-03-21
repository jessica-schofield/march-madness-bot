# filepath: /Users/jess/march-madness-bot/status/yearly_setup_reminder.py

import json
import datetime
from pathlib import Path

INCOMPLETE_CONFIG_FLAG = Path("incomplete_config.json")

def schedule_incomplete_config_reminder():
    next_morning = next_weekday_morning()
    data = {"remind_at": next_morning.isoformat()}
    INCOMPLETE_CONFIG_FLAG.write_text(json.dumps(data, indent=2))
    print(f"[INFO] Reminder scheduled for {next_morning.strftime('%A %B %d at 9:00am')} to finish Slack setup.")

def check_incomplete_config_reminder():
    if not INCOMPLETE_CONFIG_FLAG.exists():
        return
    try:
        data = json.loads(INCOMPLETE_CONFIG_FLAG.read_text())
        remind_at = datetime.datetime.fromisoformat(data["remind_at"])
        if datetime.datetime.now() >= remind_at:
            print(
                "\n⚠️  REMINDER: Your Slack setup is incomplete!\n"
                "   Run `python3 main.py` and follow the prompts to finish setting up Slack.\n"
            )
            schedule_incomplete_config_reminder()
    except Exception as e:
        print(f"[WARN] Could not read incomplete config reminder: {e}")

def clear_incomplete_config_reminder():
    if INCOMPLETE_CONFIG_FLAG.exists():
        INCOMPLETE_CONFIG_FLAG.unlink()

def next_weekday_morning():
    today = datetime.date.today()
    next_day = today + datetime.timedelta(days=1)
    return datetime.datetime.combine(next_day, datetime.time(9, 0))