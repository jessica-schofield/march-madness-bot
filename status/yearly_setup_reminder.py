import json
import datetime
import subprocess
import re
from pathlib import Path

from bot_setup.config import YEARLY_FLAG_FILE, CONFIG_FILE

FLAG_FILE = YEARLY_FLAG_FILE


def load_flag():
    """Load the yearly flag file, returning an empty dict if missing."""
    if FLAG_FILE.exists():
        try:
            return json.loads(FLAG_FILE.read_text())
        except Exception:
            return {}
    return {}


def next_weekday_morning(hour=9):
    """Return a datetime for the next weekday at the given hour."""
    now = datetime.datetime.now()
    next_day = now + datetime.timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += datetime.timedelta(days=1)
    return next_day.replace(hour=hour, minute=0, second=0, microsecond=0)


def next_business_day(date):
    """Return the next weekday (Mon–Fri) on or after the given date."""
    result = date
    while result.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        result += datetime.timedelta(days=1)
    return result


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


def _advance_tournament_dates(config):
    """
    Bump TOURNAMENT_END_MEN and TOURNAMENT_END_WOMEN forward by exactly one year
    and save to config.json. Called automatically after both championships are final.
    """
    changed = False
    for key in ("TOURNAMENT_END_MEN", "TOURNAMENT_END_WOMEN"):
        raw = config.get(key)
        if raw:
            try:
                old = datetime.date.fromisoformat(raw)
                new = old.replace(year=old.year + 1)
                config[key] = new.isoformat()
                print(f"[INFO] Advanced {key}: {old} → {new}")
                changed = True
            except ValueError:
                print(f"[WARN] Could not parse {key}={raw!r} — skipping date advance")
    if changed:
        from bot_setup.config import save_json
        save_json(CONFIG_FILE, config)
    return config


def _update_yearly_crontab(kickoff: datetime.datetime):
    """
    Replace the yearly_setup_cron.py crontab entry with one scheduled for
    March 10 of next year (or next Monday if March 10 falls on a weekend).
    No-ops gracefully if the entry is not found.
    """
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout

        # Match the yearly_setup_cron line regardless of current date fields
        pattern = re.compile(
            r"^[^\n]*yearly_setup_cron\.py[^\n]*$", re.MULTILINE
        )
        new_entry = (
            f"0 10 {kickoff.day} {kickoff.month} * "
            f"/Users/jess/march-madness-bot/venv/bin/python "
            f"/Users/jess/march-madness-bot/status/yearly_setup_cron.py "
            f">> /Users/jess/march-madness-bot/cron.log 2>&1"
        )

        if pattern.search(existing):
            updated = pattern.sub(new_entry, existing)
            print(f"[INFO] Updating yearly crontab entry to: {new_entry}")
        else:
            updated = existing.rstrip("\n") + "\n" + new_entry + "\n"
            print(f"[INFO] Adding yearly crontab entry: {new_entry}")

        proc = subprocess.run(["crontab", "-"], input=updated, text=True, capture_output=True)
        if proc.returncode == 0:
            print(f"[INFO] Crontab updated — yearly reminder set for {kickoff.strftime('%B %d %Y at %I:%M%p')}.")
        else:
            print(f"[WARN] crontab update failed: {proc.stderr.strip()}")
    except Exception as e:
        print(f"[WARN] Could not update crontab: {e}")


def check_tournament_end(config):
    """
    Called at every startup while bot is live.
    Polls ESPN to see if the men's and women's championship games are final.
    Once both are done:
      - posts a wrap-up Slack message
      - sets LIVE_FOR_YEAR=False in yearly_flag.json
      - advances TOURNAMENT_END_MEN/WOMEN by one year in config.json
      - updates the yearly crontab entry to March 10 next year
    """
    from sources.espn import check_championship_final

    flag = load_flag()

    if not flag.get("LIVE_FOR_YEAR"):
        return
    if flag.get("TOURNAMENT_ENDED"):
        return

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

    from slack_bot.slack_utils import post_message
    post_message(config, text=wrap_up, mock=mock)

    flag["LIVE_FOR_YEAR"] = False
    flag["TOURNAMENT_ENDED"] = True
    flag["STOPPED"] = False
    flag["NEXT_REMINDER"] = kickoff.isoformat()
    save_flag(flag)

    # Auto-advance dates and crontab — no manual steps needed next year
    _advance_tournament_dates(config)
    _update_yearly_crontab(kickoff)

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
        from slack_bot.slack_utils import post_message
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
        from slack_bot.slack_utils import post_message
        post_message(config, text=msg)