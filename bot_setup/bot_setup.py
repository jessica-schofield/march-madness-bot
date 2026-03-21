import json
import datetime
from asyncio import run as run_async
from pathlib import Path
import urllib.request
import urllib.parse

from bot_setup.config import CONFIG_FILE, SEEN_FILE, YEARLY_FLAG_FILE, save_json
from sources.espn import get_final_games
from sources.cbs import ensure_cbs_login, get_top_n_async, deduplicate_top_users
from slack_bot.messages import build_daily_summary, build_yearly_intro_message
from slack_bot.slack_utils import post_message
from status.yearly_setup_reminder import load_flag, next_weekday_morning
from bot_setup.setup_cli import (
    get_input_safe, ask_if_missing, ask_slack_credentials_cli,
    get_missing_config_fields, TOURNAMENT_DATES_HELP
)

PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_STATE = "playwright_state.json"
INCOMPLETE_CONFIG_FLAG = Path("incomplete_config.json")
_MAX_BROWSER_RETRIES = 3

# Championship dates by year — add each new year before the tournament starts.
# Men's final = first Monday in April; Women's final = Sunday before.
_TOURNAMENT_DATES = {
    2024: {"men": datetime.date(2024, 4, 8), "women": datetime.date(2024, 4, 7)},
    2025: {"men": datetime.date(2025, 4, 7), "women": datetime.date(2025, 4, 6)},
    2026: {"men": datetime.date(2026, 4, 6), "women": datetime.date(2026, 4, 5)},
}

def _default_tournament_end(gender: str) -> datetime.date:
    """Return the championship date for the current year, or warn and fall back."""
    year = datetime.date.today().year
    dates = _TOURNAMENT_DATES.get(year)
    if dates:
        return dates[gender]
    # Fall back to the most recent known year and warn
    latest_year = max(_TOURNAMENT_DATES)
    print(
        f"[WARN] No tournament dates configured for {year}. "
        f"Add them to _TOURNAMENT_DATES in bot_setup.py. "
        f"Using {latest_year} dates as a fallback."
    )
    return _TOURNAMENT_DATES[latest_year][gender]


_DEFAULT_TOURNAMENT_END_MEN = _default_tournament_end("men")
_DEFAULT_TOURNAMENT_END_WOMEN = _default_tournament_end("women")


def _tournament_end(config, gender):
    key = "TOURNAMENT_END_MEN" if gender == "men's" else "TOURNAMENT_END_WOMEN"
    default = _DEFAULT_TOURNAMENT_END_MEN if gender == "men's" else _DEFAULT_TOURNAMENT_END_WOMEN
    raw = config.get(key)
    if raw:
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            print(f"[WARN] Invalid {key} in config: '{raw}' — using default.")
    return default


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


def _clean_url(url):
    if not url:
        return url
    url = url.strip()
    if url.startswith("<") and url.endswith(">"):
        url = url[1:-1]
    if "|" in url:
        url = url.split("|")[0]
    return url


def _is_placeholder_url(url):
    """Return True if the URL is a placeholder that hasn't been configured yet."""
    if not url:
        return True
    from urllib.parse import urlparse
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.lower()

    if "example.com" in netloc:
        return True

    # Old fake CBS paths used before picks.cbssports.com was known
    if "cbssports.com" in netloc and path in (
        "/brackets/men/group/123",
        "/brackets/women/group/456",
    ):
        return True

    if "script.google.com/fake" in url:
        return True

    if url == "https://hooks.slack.com/services/TEST":
        return True

    return False


def _ask_bracket_url_via_dm(user_id, gender_label, config, pool):
    from slack_bot.slack_dm import send_dm, poll_for_reply, save_pending_dm

    tournament_end = _tournament_end(config, gender_label)
    url_key = "MEN_URL" if gender_label == "men's" else "WOMEN_URL"

    existing = pool.get(url_key, "")
    if existing and "example.com" not in existing:  # ← ignore placeholders
        return existing

    emoji = "🏆" if gender_label == "men's" else "👑"
    question = (
        f"{emoji} Do you have a *{gender_label} bracket pool* to track? Paste the standings URL "
        f"from CBS, ESPN, Yahoo — wherever your pool lives!\n"
        f"Reply with the URL, `no` to be reminded tomorrow, or `stop` to skip this forever."
    )

    channel_id, question_ts = send_dm(user_id, question)

    if channel_id is None:
        print(f"[WARN] Could not open DM channel with {user_id} — skipping {gender_label} URL prompt.")
        return None

    reply = poll_for_reply(channel_id, question_ts, timeout_seconds=1800)

    if reply is None:
        next_morning = next_weekday_morning()
        send_dm(
            user_id,
            f"⏰ No response — I'll ask again tomorrow at *{next_morning.strftime('%A %B %d at 9:00am')}*. 👋\n"
            f"_(Reply `stop` at any time to stop these reminders.)_"
        )
        save_pending_dm(user_id, question, None, optional=True)
        return None

    reply_lower = reply.strip().lower()

    if reply_lower == "stop":
        send_dm(user_id, f"👍 Got it — I won't ask about the {gender_label} bracket again.")
        pool[url_key] = ""
        return ""

    if reply_lower == "no":
        if datetime.date.today() >= tournament_end:
            send_dm(user_id, f"🏁 The tournament is over — no more reminders for the {gender_label} bracket!")
            pool[url_key] = ""
            return ""
        next_morning = next_weekday_morning()
        send_dm(
            user_id,
            f"👍 No problem! I'll ask again tomorrow at *{next_morning.strftime('%A %B %d at 9:00am')}*.\n"
            f"_(Reply `stop` at any time to stop these reminders.)_"
        )
        save_pending_dm(user_id, question, None, optional=True)
        return None

    cleaned = _clean_url(reply.strip())
    pool[url_key] = cleaned
    return cleaned


def run_slack_dm_setup(config):
    from slack_bot.slack_dm import ask_via_dm, send_dm, send_dm_blocks, clear_pending_dm

    user_id = config.get("SLACK_MANAGER_ID")
    if not user_id:
        print("[ERROR] run_slack_dm_setup called without SLACK_MANAGER_ID in config.")
        return None

    send_dm(
        user_id,
        "👋 Hey! I'm your March Madness Bot — let's get you set up! 🏆\n"
        "I'll ask a few quick questions. Just reply to each one, or type `skip` to use the default."
    )

    reply = ask_via_dm(
        user_id, "🏅 How many top bracket players should I show on the leaderboard? (e.g. 5 or 10)", default=5)
    if reply is None:
        return None
    try:
        config["TOP_N"] = int(reply)
    except (ValueError, TypeError):
        config["TOP_N"] = 5

    reply = ask_via_dm(
        user_id, "🚨 Want me to send a message every time a game goes final? Reply `yes` or `no`", default="yes")
    if reply is None:
        return None
    config["SEND_GAME_UPDATES"] = reply.strip().lower() in ("yes", "y")

    reply = ask_via_dm(
        user_id, "☀️ Should I send a daily morning summary of the previous day's games? Reply `yes` or `no`", default="yes")
    if reply is None:
        return None
    config["SEND_DAILY_SUMMARY"] = reply.strip().lower() in ("yes", "y")

    if config.get("SEND_GAME_UPDATES"):
        reply = ask_via_dm(
            user_id,
            "⏱️ How often should I send game updates?\n"
            "• Reply `live` to post every game the moment it's final 🔴\n"
            "• Or reply with a number of minutes to batch them (e.g. `30` or `60`)",
            default="live"
        )
        if reply is None:
            return None
        reply_clean = reply.strip().lower()
        if reply_clean in ("live", "0", "skip"):
            config["MINUTES_BETWEEN_MESSAGES"] = 0
        else:
            try:
                config["MINUTES_BETWEEN_MESSAGES"] = int(reply_clean)
            except (ValueError, TypeError):
                config["MINUTES_BETWEEN_MESSAGES"] = 0
    else:
        config["MINUTES_BETWEEN_MESSAGES"] = 0

    reply = ask_via_dm(
        user_id, "📅 Should I post on weekends too? The madness doesn't stop... Reply `yes` or `no`", default="no")
    if reply is None:
        return None
    config["POST_WEEKENDS"] = reply.strip().lower() in ("yes", "y")

    config.setdefault("POOLS", [{"SOURCE": "custom"}])
    if not config["POOLS"]:
        print("[ERROR] No POOLS configured — cannot continue.")
        return config
    pool = config["POOLS"][0]

    men_url = _ask_bracket_url_via_dm(user_id, "men's", config, pool)
    if men_url is None:
        save_json(CONFIG_FILE, config)
        return None

    women_url = _ask_bracket_url_via_dm(user_id, "women's", config, pool)
    if women_url is None:
        save_json(CONFIG_FILE, config)
        return None

    config.setdefault("TOURNAMENT_END_MEN", _DEFAULT_TOURNAMENT_END_MEN.isoformat())
    config.setdefault("TOURNAMENT_END_WOMEN", _DEFAULT_TOURNAMENT_END_WOMEN.isoformat())

    config["PLAYWRIGHT_HEADLESS"] = PLAYWRIGHT_HEADLESS
    config["PLAYWRIGHT_STATE"] = PLAYWRIGHT_STATE

    save_json(CONFIG_FILE, config)
    clear_pending_dm()
    return config


def _fetch_leaderboard(pool, gender, config, method):
    url_key = "MEN_URL" if gender == "men" else "WOMEN_URL"
    gender_label = "men's" if gender == "men" else "women's"
    url = pool.get(url_key)

    if not url or _is_placeholder_url(url):  # skip placeholders, not just empty
        return []

    top_n = config.get("TOP_N", 5)
    max_results = int(top_n * 1.5)
    state = config.get("PLAYWRIGHT_STATE", PLAYWRIGHT_STATE)
    try:
        print(f"[INFO] Fetching {gender_label} leaderboard...")
        results = run_async(get_top_n_async(url, top_n, playwright_state=state))
        if len(results) > max_results:
            print(f"[INFO] Trimmed {gender_label} leaderboard from {len(results)} to {max_results} (1.5x TOP_N cap).")
            results = results[:max_results]
        print(f"[INFO] {gender_label.capitalize()} top {len(results)} fetched: {results}")
        return results
    except Exception as e:
        print(f"[WARN] Failed to fetch {gender_label} leaderboard: {e}")
        if method == "slack" and config.get("SLACK_MANAGER_ID"):
            from slack_bot.slack_dm import send_dm, ask_manual_top_users
            send_dm(
                config["SLACK_MANAGER_ID"],
                f"⚠️ Couldn't scrape the {gender_label} leaderboard:\n```{e}```"
            )
            return ask_manual_top_users(config["SLACK_MANAGER_ID"], gender_label, config.get("TOP_N", 5))
        return []


def run_setup(existing_config=None):
    config = existing_config or {}

    print("\n--- March Madness Bot Setup ---\n")

    # Always ask — never skip based on saved config
    method = get_input_safe(
        "Do you want to configure via Slack or Command Line? (slack/cli)",
        default="slack",
        config=config
    ).lower()

    if method not in ("slack", "cli"):
        print(f"[WARN] Unknown method '{method}' — defaulting to cli.")
        method = "cli"

    config["METHOD"] = method

    if method == "slack":
        print("\n[INFO] First I need two things to connect to Slack, then I'll switch to DMs for the rest.\n")
        config = ask_slack_credentials_cli(config)
        save_json(CONFIG_FILE, config)

        if config.get("SLACK_WEBHOOK_URL") and config.get("SLACK_MANAGER_ID"):
            print(f"\n[INFO] Credentials saved. Switching to Slack DMs with {config['SLACK_MANAGER_ID']}...")
            result = run_slack_dm_setup(config)
            if result is None:
                print("[INFO] Setup paused — will resume via DM tomorrow morning.")
                schedule_incomplete_config_reminder()
                return None, method, [], [], [], []
            config = result
        else:
            print("[WARN] Missing webhook or user ID — falling back to CLI setup.")
            method = "cli"

    if method == "cli":
        # Always ask for credentials first — required before anything else
        config = ask_slack_credentials_cli(config)
        save_json(CONFIG_FILE, config)

        if not config.get("SLACK_WEBHOOK_URL"):
            print("[WARN] No Slack webhook URL provided — cannot go live without it.")
            return config, method, [], [], [], []

        ask_if_missing(config, "TOP_N", "How many top users to display?", default="5", cast=int)
        ask_if_missing(config, "MINUTES_BETWEEN_MESSAGES", "Minutes between messages?", default="60", cast=int)
        ask_if_missing(config, "POST_WEEKENDS", "Post on weekends? (y/n)", default="n", cast=lambda x: x.lower() == "y")
        ask_if_missing(config, "SEND_GAME_UPDATES", "Send game-by-game updates? (y/n)",
                       default="y", cast=lambda x: x.lower() == "y")
        ask_if_missing(config, "SEND_DAILY_SUMMARY", "Send daily summary? (y/n)",
                       default="y", cast=lambda x: x.lower() == "y")
        ask_if_missing(
            config, "TOURNAMENT_END_MEN",
            "Men's championship date (YYYY-MM-DD)?",
            default=_DEFAULT_TOURNAMENT_END_MEN.isoformat()
        )
        ask_if_missing(
            config, "TOURNAMENT_END_WOMEN",
            "Women's championship date (YYYY-MM-DD)?",
            default=_DEFAULT_TOURNAMENT_END_WOMEN.isoformat()
        )

        config["PLAYWRIGHT_HEADLESS"] = PLAYWRIGHT_HEADLESS
        config["PLAYWRIGHT_STATE"] = PLAYWRIGHT_STATE

        config.setdefault("POOLS", [{"SOURCE": "custom"}])
        if not config["POOLS"]:
            print("[ERROR] No POOLS configured — cannot continue. Add pool URLs and run setup again.")
            return config, config.get("METHOD", "cli"), [], [], [], []
        pool = config["POOLS"][0]

        # prompt if missing OR still a placeholder
        if not pool.get("MEN_URL") or _is_placeholder_url(pool.get("MEN_URL")):
            pool["MEN_URL"] = get_input_safe(
                "Paste your men's bracket pool standings URL (CBS, ESPN, Yahoo, etc.), or leave blank to skip",
                config=config
            )
        if not pool.get("WOMEN_URL") or _is_placeholder_url(pool.get("WOMEN_URL")):
            pool["WOMEN_URL"] = get_input_safe(
                "Paste your women's bracket pool standings URL (CBS, ESPN, Yahoo, etc.), or leave blank to skip",
                config=config
            )

        if not pool.get("MEN_URL") and not pool.get("WOMEN_URL"):
            if get_input_safe(
                "No bracket URLs set. Enter manual top users instead? (y/n)",
                default="n",
                config=config
            ).lower() == "y":
                config["MANUAL_TOP"] = []
            else:
                config["MANUAL_TOP"] = None

        save_json(CONFIG_FILE, config)

    # second guard after both method branches
    config.setdefault("POOLS", [{"SOURCE": "custom"}])
    if not config["POOLS"]:
        print("[ERROR] No POOLS configured — cannot continue. Add pool URLs and run setup again.")
        return config, config.get("METHOD", "cli"), [], [], [], []  # 6-tuple, not None

    pool = config["POOLS"][0]

    # block go-live if URLs are still placeholders after prompting
    men_url = pool.get("MEN_URL", "")
    women_url = pool.get("WOMEN_URL", "")
    urls_configured = not (_is_placeholder_url(men_url) and _is_placeholder_url(women_url))
    manual_top_set = bool(config.get("MANUAL_TOP"))

    if not urls_configured and not manual_top_set:
        print(
            "[WARN] No bracket URLs configured and no manual top users set.\n"
            "[INFO] Re-run setup and paste your bracket pool URLs to go live."
        )
        save_json(CONFIG_FILE, config)
        return config, method, [], [], [], []

    print("\n[INFO] Fetching yesterday's games...")
    men_games = get_final_games("men") or []
    women_games = get_final_games("women") or []

    if men_games:
        print(f"[INFO] Found {len(men_games)} men's game(s).")
    else:
        print("[WARN] No men's games found for yesterday.")

    if women_games:
        print(f"[INFO] Found {len(women_games)} women's game(s).")
    else:
        print("[WARN] No women's games found for yesterday.")

    top_men, top_women = [], []
    if pool.get("MEN_URL") or pool.get("WOMEN_URL"):
        state_path = Path(PLAYWRIGHT_STATE)

        men_url = pool.get("MEN_URL", "")
        women_url = pool.get("WOMEN_URL", "")
        if _is_placeholder_url(men_url) and _is_placeholder_url(women_url):
            print("[WARN] Both pool URLs are placeholders — skipping browser login.")
        else:
            if not state_path.exists() or state_path.stat().st_size < 500:
                if state_path.exists():
                    state_path.unlink()
                    print("[INFO] Old session was invalid, deleting...")

                browser_success = False
                retries = 0
                while not browser_success and retries < _MAX_BROWSER_RETRIES:  # fix 3: bounded loop
                    print("[INFO] Opening browser for leaderboard login...")
                    if method == "slack" and config.get("SLACK_MANAGER_ID"):
                        from slack_bot.slack_dm import send_dm, poll_for_reply
                        send_dm(
                            config["SLACK_MANAGER_ID"],
                            "🌐 Opening a browser window on your computer so you can log in to your bracket site.\n\n"
                            "1. Log in to CBS (or wherever your pool is)\n"
                            "2. Once you're logged in, reply `done` here and I'll take it from there! 👇"
                        )
                    try:
                        run_async(ensure_cbs_login(
                            pool,
                            PLAYWRIGHT_STATE,
                            slack_user_id=config.get("SLACK_MANAGER_ID") if method == "slack" else None
                        ))
                        browser_success = True
                    except Exception as e:
                        retries += 1
                        print(f"[WARN] Browser login failed: {e}")
                        if method == "slack" and config.get("SLACK_MANAGER_ID"):
                            from slack_bot.slack_dm import send_dm, poll_for_reply, ask_manual_top_users
                            channel_id, ts = send_dm(
                                config["SLACK_MANAGER_ID"],
                                f"⚠️ Browser login failed:\n```{e}```\n\n"
                                f"Reply `retry` to try again, or `manual` to enter the leaderboard yourself."
                            )
                            if channel_id is None:
                                print("[WARN] Could not send browser failure DM — aborting login loop.")
                                break
                            reply = poll_for_reply(channel_id, ts, timeout_seconds=300)
                            if reply and reply.strip().lower() == "retry":
                                send_dm(config["SLACK_MANAGER_ID"], "👍 Retrying — watch for the browser window!")
                                continue
                            else:
                                send_dm(config["SLACK_MANAGER_ID"], "👍 No problem — let's do it manually!")
                                top_men = ask_manual_top_users(config["SLACK_MANAGER_ID"], "men's", config.get("TOP_N", 5))
                                top_women = ask_manual_top_users(
                                    config["SLACK_MANAGER_ID"], "women's", config.get("TOP_N", 5))
                                browser_success = True
                                break
                        else:
                            choice = get_input_safe(
                                "Browser login failed. Try again or enter manually? (retry/manual)",
                                default="retry",
                                config=config
                            ).lower()
                            if choice == "retry":
                                continue
                            else:
                                break

            else:
                print("[INFO] Browser session found.")

        if not top_men:
            top_men = _fetch_leaderboard(pool, "men", config, method)
        if not top_women:
            top_women = _fetch_leaderboard(pool, "women", config, method)

    top_men = deduplicate_top_users(top_men)
    top_women = deduplicate_top_users(top_women)

    blocks, no_games = build_daily_summary(
        men_games, women_games, top_men, top_women,
        men_url=pool.get("MEN_URL"),
        women_url=pool.get("WOMEN_URL"),
        top_n=config.get("TOP_N", 5)
    )

    go_live = False

    if method == "slack" and config.get("SLACK_MANAGER_ID"):
        from slack_bot.slack_dm import send_dm, send_dm_blocks, poll_for_reply, save_pending_dm
        user_id = config["SLACK_MANAGER_ID"]
        send_dm(user_id, "✅ Setup complete! Here's a preview of what your daily message will look like:")
        send_dm_blocks(user_id, blocks)

        channel_id, question_ts = send_dm(
            user_id,
            "Ready to go live? Reply `yes` to activate the bot, or `no` and I'll check back tomorrow morning."
        )

        if channel_id is None:
            print("[WARN] Could not send go-live DM — deferring.")
            save_json(CONFIG_FILE, config)
            return config, method, men_games, women_games, top_men, top_women

        reply = poll_for_reply(channel_id, question_ts, timeout_seconds=1800)

        if reply is None or reply.strip().lower() in ("no", "n"):
            next_morning = next_weekday_morning()
            send_dm(
                user_id,
                f"👍 No problem! I'll check back in at *{next_morning.strftime('%A %B %d at 9:00am')}*. 👋\n"
                f"_(Reply `stop` at any time to stop these reminders.)_"
            )
            if reply is not None and reply.strip().lower() != "stop":
                save_pending_dm(
                    user_id,
                    "Ready to go live? Reply `yes` to activate the bot, or `no` and I'll check back tomorrow morning.",
                    None,
                    optional=True
                )
            save_json(CONFIG_FILE, config)
            print("[INFO] Go-live deferred — will ask again tomorrow morning.")
            return config, method, men_games, women_games, top_men, top_women

        go_live = reply.strip().lower() in ("yes", "y")

    else:
        print("\n--- Preview of your daily message ---")
        for block in blocks:
            text = block.get("text", {}).get("text", "")
            if text:
                print(text)
        print("-------------------------------------\n")

        confirm = get_input_safe(
            "Ready to go live? This will post the intro + today's summary to Slack (y/n)",
            default="y",
            config=config
        ).lower()
        go_live = confirm in ("y", "yes")

        if not go_live:
            print("[INFO] Go-live skipped. Run again when you're ready.")
            save_json(CONFIG_FILE, config)
            return config, method, men_games, women_games, top_men, top_women

    if go_live:
        _ping_live_counter(config)
        mock_mode = not bool(config.get("SLACK_WEBHOOK_URL"))
        post_message(config, text=build_yearly_intro_message(config), mock=mock_mode)

        if not no_games:
            post_message(config, blocks=blocks, mock=mock_mode)

        yearly_flag = load_flag()
        yearly_flag["LIVE_FOR_YEAR"] = True
        save_json(YEARLY_FLAG_FILE, yearly_flag)

        all_games = (men_games or []) + (women_games or [])
        save_json(SEEN_FILE, list(set(g["id"] for g in all_games)))

        if method == "slack" and config.get("SLACK_MANAGER_ID"):
            from slack_bot.slack_dm import send_dm
            send_dm(
                config["SLACK_MANAGER_ID"],
                "🎉🏆 *We're LIVE!* The bot is now active for the tournament!\n\n"
                "📬 Check your bracket channel — the first message just posted!\n\n"
                "🏀🔥 May the best bracket win!"
            )

        if not get_missing_config_fields(config):
            clear_incomplete_config_reminder()

        save_json(CONFIG_FILE, config)
        print("[INFO] Bot is now live!")

    return config, method, men_games, women_games, top_men, top_women


def _ping_live_counter(config: dict) -> None:
    url = config.get("LIVE_COUNTER_URL", "")
    if not url:
        return
    try:
        year = datetime.datetime.now().year
        version = config.get("VERSION", "unknown")
        params = urllib.parse.urlencode({"year": year, "version": version})
        full_url = f"{url}?{params}"

        with urllib.request.urlopen(full_url, timeout=10) as resp:
            data = json.loads(resp.read())
            print(
                f"[INFO] 🎉 Bot live! {data.get('thisYear', '?')} bot(s) live in {year}, {data.get('total', '?')} all-time.")
    except Exception:
        pass
