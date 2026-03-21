import json
import datetime
from pathlib import Path

from config import YEARLY_FLAG_FILE  # ← add this import

FLAG_FILE = YEARLY_FLAG_FILE  # ← replace: FLAG_FILE = Path("yearly_flag.json")
                               # or replace all FLAG_FILE usages with YEARLY_FLAG_FILE directly


def load_flag():
    """Load the yearly flag file, returning an empty dict if missing."""
    if FLAG_FILE.exists():
        try:
            return json.loads(FLAG_FILE.read_text())
        except Exception:
            return {}
    return {}


def next_weekday_morning(hour=9):
    """Return a datetime for 9am on the next weekday."""
    now = datetime.datetime.now()
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += datetime.timedelta(days=1)
    # skip Saturday (5) and Sunday (6)
    while candidate.weekday() >= 5:
        candidate += datetime.timedelta(days=1)
    return candidate


def needs_config_reminder(config, last_reminded_at=None):
    """
    Return True if config is incomplete and at least 24h have passed since last reminder.
    last_reminded_at: a datetime object, or None if never reminded.
    Moved here from slack_utils.py — this is where reminder scheduling logic lives.
    """
    incomplete = not config.get("SLACK_WEBHOOK_URL") or not config.get("SLACK_MANAGER_ID")
    if not incomplete:
        return False

    if last_reminded_at is None:
        return True

    if not isinstance(last_reminded_at, datetime.datetime):
        print(f"[WARN] needs_config_reminder: expected datetime, got {type(last_reminded_at)}")
        return True

    return (datetime.datetime.now() - last_reminded_at).total_seconds() > 24 * 3600


def save_flag(flag):
    FLAG_FILE.write_text(json.dumps(flag, indent=2, default=str))


def next_year_kickoff():
    """Return 10am on March 10 next year, rolling forward to Monday if it's a weekend."""
    next_year = datetime.datetime.now().year + 1
    kickoff = datetime.datetime(next_year, 3, 10, 10, 0, 0)
    while kickoff.weekday() >= 5:
        kickoff += datetime.timedelta(days=1)
    return kickoff


def check_tournament_end(config):
    """
    Called at every startup while bot is live.
    Polls ESPN to see if the men's and women's championship games are final.
    Once both are done, posts a wrap-up message and schedules next year's reminder.
    Caches results in yearly_flag.json so we don't re-fire after wrap-up is sent.
    """
    from espn import check_championship_final

    flag = load_flag()

    if not flag.get("LIVE_FOR_YEAR"):
        return
    if flag.get("TOURNAMENT_ENDED"):
        return

    # Check each gender — cache results so we don't lose them on the next run
    if not flag.get("MEN_CHAMPIONSHIP_DATE"):
        men_date = check_championship_final("men")
        if men_date:
            flag["MEN_CHAMPIONSHIP_DATE"] = men_date.isoformat()
            save_flag(flag)
            print(f"[INFO] Men's championship final confirmed: {men_date}")

    if not flag.get("WOMEN_CHAMPIONSHIP_DATE"):
        women_date = check_championship_final("women")
        if women_date:
            flag["WOMEN_CHAMPIONSHIP_DATE"] = women_date.isoformat()
            save_flag(flag)
            print(f"[INFO] Women's championship final confirmed: {women_date}")

    men_done = flag.get("MEN_CHAMPIONSHIP_DATE")
    women_done = flag.get("WOMEN_CHAMPIONSHIP_DATE")

    if not men_done or not women_done:
        # At least one tournament still in progress
        missing = []
        if not men_done:
            missing.append("men's")
        if not women_done:
            missing.append("women's")
        print(f"[INFO] Still waiting on: {', '.join(missing)} championship")
        return

    # Both are done — wrap up
    men_str = datetime.date.fromisoformat(men_done).strftime("%B %d")
    women_str = datetime.date.fromisoformat(women_done).strftime("%B %d")
    kickoff = next_year_kickoff()

    print("[INFO] Both championships are final — wrapping up.")
    mock = not bool(config.get("SLACK_WEBHOOK_URL"))

    wrap_up = (
        "🏆 *That's a wrap on March Madness!* Both tournaments are over.\n\n"
        f"  🏀 Men's championship: *{men_str}*\n"
        f"  👑 Women's championship: *{women_str}*\n\n"
        "The bot is going to sleep until next year. 😴\n"
        f"I'll remind you to set up again on *{kickoff.strftime('%A, %B %d %Y')} at 10:00am*. "
        "See you then! 🏀"
    )

    from slack_utils import post_message
    post_message(config, text=wrap_up, mock=mock)

    flag["LIVE_FOR_YEAR"] = False
    flag["TOURNAMENT_ENDED"] = True
    flag["STOPPED"] = False
    flag["NEXT_REMINDER"] = kickoff.isoformat()
    save_flag(flag)
    print(f"[INFO] Next-year reminder scheduled for {kickoff.strftime('%A %B %d %Y at 10:00am')}.")


def yearly_reminder(config, manager_id):
    flag = load_flag()

    if flag.get("STOPPED"):
        return
    if flag.get("LIVE_FOR_YEAR"):
        return

    now = datetime.datetime.now()
    today = now.date()

    next_reminder = flag.get("NEXT_REMINDER")
    if next_reminder:
        next_dt = datetime.datetime.fromisoformat(next_reminder)
        if now < next_dt:
            print(f"[INFO] Next reminder scheduled for {next_dt.strftime('%A %B %d at %I:%M%p')}")
            return

    next_morning = next_weekday_morning()
    flag["NEXT_REMINDER"] = next_morning.isoformat()
    save_flag(flag)

    mock = not bool(config.get("SLACK_WEBHOOK_URL"))

    if flag.get("TOURNAMENT_ENDED"):
        reminder_text = (
            f"👋 Hey! It's almost time for March Madness {today.year}! 🏀\n"
            "Run `python3 main.py` to set up this year's bracket bot and go live.\n\n"
            "_(I'll remind you each weekday until both tournaments end. "
            "Reply `stop` to stop these reminders.)_"
        )
    else:
        reminder_text = (
            "👋 Hey! The March Madness bot hasn't been set up yet for this year.\n"
            "Run `python3 main.py` to finish setup and go live.\n\n"
            "_(I'll keep reminding you each weekday until both tournaments end. "
            "Reply `stop` to stop these reminders.)_"
        )

    if mock:
        print(f"\n[REMINDER — MOCK SLACK]\n{reminder_text}")
        print(f"Next reminder: {next_morning.strftime('%A %B %d at 9:00am')}\n")
    else:
        from slack_utils import post_message
        post_message(config, text=reminder_text)
        print(f"[INFO] Reminder sent. Next: {next_morning.strftime('%A %B %d at 9:00am')}.")


def handle_stop(config):
    flag = load_flag()
    flag["STOPPED"] = True
    save_flag(flag)
    mock = not bool(config.get("SLACK_WEBHOOK_URL"))
    msg = "✅ Got it — no more March Madness reminders. Run `python3 main.py` any time to set up manually."
    if mock:
        print(f"[MOCK SLACK] {msg}")
    else:
        from slack_utils import post_message
        post_message(config, text=msg)