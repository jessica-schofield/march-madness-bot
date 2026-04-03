#!/usr/bin/env python3
# ------------------------------
# MARCH MADNESS BOT
# ------------------------------

import sys
import fcntl
from asyncio import run as run_async
from pathlib import Path
import datetime

from bot_setup.config import CONFIG_FILE, SEEN_FILE, LAST_POST_FILE, YEARLY_FLAG_FILE, LAST_RANKINGS_FILE, load_json, save_json, needs_setup, missing_setup_keys
from bot_setup.bot_setup import run_setup, PLAYWRIGHT_STATE
from sources.espn import get_final_games
from sources.cbs import ensure_cbs_login, get_top_n_async, deduplicate_top_users
from slack_bot.messages import build_daily_summary, build_slack_message
from slack_bot.slack_utils import post_message
from slack_bot.slack_dm import send_dm, ask_manual_top_users
from status.yearly_setup_reminder import yearly_reminder, handle_stop, check_tournament_end, needs_config_reminder

LOCK_FILE = Path(__file__).parent / "bot.lock"


def run(config=None, yearly_flag=None):
    """Main bot logic — extracted for testability."""
    if config is None:
        config = load_json(CONFIG_FILE, {})
    if yearly_flag is None:
        yearly_flag = load_json(YEARLY_FLAG_FILE, {})

    check_tournament_end(config)

    already_live = yearly_flag.get("LIVE_FOR_YEAR", False)

    if needs_setup(config) or not already_live:
        import sys
        if not sys.stdin.isatty():
            missing = missing_setup_keys(config)
            if missing:
                print(f"[ERROR] Bot config is incomplete — cannot run setup non-interactively.")
                print(f"[ERROR] Missing or empty fields: {', '.join(missing)}")
            else:
                print("[ERROR] LIVE_FOR_YEAR not set — cannot run yearly setup non-interactively.")
            print("[ERROR] Run 'python main.py' in a terminal to complete setup.")
            return
        print("[INFO] Config incomplete — running setup...")
        setup_config = dict(config)
        result = run_setup(setup_config)
        if result is None or result[0] is None:
            print("[INFO] Setup incomplete — exiting.")
            return
        config, _, men_games, women_games, top_men, top_women = result
        yearly_flag = load_json(YEARLY_FLAG_FILE, {})  # reload after setup writes LIVE_FOR_YEAR
    else:
        # Daily recap is always based on yesterday's games.
        men_games = get_final_games("men", days_ago=1)
        women_games = get_final_games("women", days_ago=1)

        # Live game updates should include today's finals; keep yesterday as a fallback
        # to avoid missing late-night finals around timezone boundaries.
        men_games_updates = get_final_games("men", days_ago=0) + men_games
        women_games_updates = get_final_games("women", days_ago=0) + women_games

        top_men, top_women = [], []
        pool = config.get("POOLS", [{}])[0]
        manager_id = config.get("SLACK_MANAGER_ID", "")

        if not pool.get("MEN_URL") and not pool.get("WOMEN_URL"):
            warning = (
                "No MEN_URL or WOMEN_URL configured — leaderboard scraping is disabled, "
                "so movers will show no changes unless cached rankings exist."
            )
            print(f"[WARN] {warning}")
            if manager_id:
                try:
                    send_dm(manager_id, f"⚠️ {warning}")
                except Exception as e:
                    print(f"[WARN] Failed to DM manager about missing pool URLs: {e}")

        if pool.get("MEN_URL") or pool.get("WOMEN_URL"):
            try:
                run_async(ensure_cbs_login(pool, PLAYWRIGHT_STATE))
            except Exception as e:
                print(f"[WARN] Browser login failed: {e}")
                if manager_id:
                    send_dm(manager_id, f"⚠️ March Madness Bot error — browser login failed:\n```{e}```")

            try:
                if pool.get("MEN_URL"):
                    top_men = run_async(get_top_n_async(pool["MEN_URL"], config.get("TOP_N", 5), PLAYWRIGHT_STATE))
            except Exception as e:
                print(f"[WARN] Failed to fetch men's leaderboard: {e}")
                if manager_id:
                    send_dm(manager_id, f"⚠️ Couldn't scrape the men's leaderboard:\n```{e}```")
                    top_men = ask_manual_top_users(manager_id, "men's", config.get("TOP_N", 5))

            try:
                if pool.get("WOMEN_URL"):
                    top_women = run_async(get_top_n_async(pool["WOMEN_URL"], config.get("TOP_N", 5), PLAYWRIGHT_STATE))
            except Exception as e:
                print(f"[WARN] Failed to fetch women's leaderboard: {e}")
                if manager_id:
                    send_dm(manager_id, f"⚠️ Couldn't scrape the women's leaderboard:\n```{e}```")
                    top_women = ask_manual_top_users(manager_id, "women's", config.get("TOP_N", 5))

        top_men = deduplicate_top_users(top_men)
        top_women = deduplicate_top_users(top_women)

        _last = load_json(LAST_RANKINGS_FILE, {"men": [], "women": []})
        display_men = top_men or _last.get("men", [])
        display_women = top_women or _last.get("women", [])

        mock = not bool(config.get("SLACK_WEBHOOK_URL"))
        if config.get("SEND_DAILY_SUMMARY", True):
            last_post = load_json(LAST_POST_FILE, {})
            last_post_date = last_post.get("date")
            today_str = datetime.date.today().isoformat()
            summary_hour = config.get("SUMMARY_HOUR", 9)
            if last_post_date != today_str and datetime.datetime.now().hour >= summary_hour:
                blocks, is_rest_day = build_daily_summary(
                    men_games, women_games, top_men, top_women,
                    men_url=pool.get("MEN_URL"),
                    women_url=pool.get("WOMEN_URL"),
                    top_n=config.get("TOP_N", 5)
                )
                post_message(config, blocks=blocks, mock=mock)
                save_json(LAST_POST_FILE, {"date": today_str, "time": datetime.datetime.now().isoformat()})
            elif last_post_date == today_str:
                print(f"[INFO] Daily summary already posted today ({today_str}) — skipping.")
            else:
                print(f"[INFO] Daily summary will post after {summary_hour}:00 — skipping for now.")

        if config.get("SEND_GAME_UPDATES", True):
            seen = load_json(SEEN_FILE, [])
            if not isinstance(seen, list):
                seen = []
            all_update_games = []
            seen_ids = set()
            for g in (men_games_updates + women_games_updates):
                gid = g.get("id")
                if gid in seen_ids:
                    continue
                seen_ids.add(gid)
                all_update_games.append(g)

            unseen = [g for g in all_update_games if g["id"] not in seen]
            for game in unseen:
                blocks = build_slack_message(
                    game, display_men, display_women,
                    men_url=pool.get("MEN_URL"),
                    women_url=pool.get("WOMEN_URL")
                )
                post_message(config, blocks=blocks, mock=mock)
                seen.append(game["id"])
            if unseen:
                save_json(SEEN_FILE, seen)

    if not yearly_flag.get("LIVE_FOR_YEAR"):
        manager_id = config.get("SLACK_MANAGER_ID", "")
        yearly_reminder(config, manager_id)

    if not yearly_flag.get("LIVE_FOR_YEAR"):
        last_post = load_json(LAST_POST_FILE, {})
        last_post_dt = None
        if isinstance(last_post, dict) and last_post.get("time"):
            try:
                last_post_dt = datetime.datetime.fromisoformat(last_post["time"])
            except ValueError:
                pass
        if needs_config_reminder(config, last_post_dt):
            print("[REMIND] Config incomplete — please finish setup.")

    print("[INFO] Done.")


if __name__ == "__main__":
    print("[INFO] March Madness Bot starting...")

    if len(sys.argv) > 1 and sys.argv[1].lower() == "stop":
        config = load_json(CONFIG_FILE, {})
        handle_stop(config)
        sys.exit(0)

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[INFO] Another instance is already running — exiting.")
        sys.exit(0)

    try:
        run()
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()