#!/usr/bin/env python3
# ------------------------------
# MARCH MADNESS BOT
# ------------------------------

import sys
from asyncio import run as run_async
from pathlib import Path

from bot_setup.config import CONFIG_FILE, SEEN_FILE, LAST_POST_FILE, YEARLY_FLAG_FILE, load_json, save_json, needs_setup
from bot_setup.bot_setup import run_setup, PLAYWRIGHT_STATE
from sources.espn import get_final_games
from sources.cbs import ensure_cbs_login, get_top_n_async, deduplicate_top_users
from slack_bot.messages import build_daily_summary
from slack_bot.slack_utils import post_message
from slack_bot.slack_dm import send_dm, ask_manual_top_users
from status.yearly_setup_reminder import yearly_reminder, handle_stop, check_tournament_end, needs_config_reminder


def run(config=None, yearly_flag=None):
    """Main bot logic — extracted for testability."""
    if config is None:
        config = load_json(CONFIG_FILE, {})
    if yearly_flag is None:
        yearly_flag = load_json(YEARLY_FLAG_FILE, {})

    check_tournament_end(config)

    if needs_setup(config) or not yearly_flag.get("LIVE_FOR_YEAR"):
        print("[INFO] Config incomplete — running setup...")
        setup_config = {k: v for k, v in config.items() if k != "METHOD"}
        result = run_setup(setup_config)
        if result is None or result[0] is None:
            print("[INFO] Setup incomplete — exiting.")
            return
        config, _, men_games, women_games, top_men, top_women = result
    else:
        men_games = get_final_games("men")
        women_games = get_final_games("women")

        top_men, top_women = [], []
        pool = config.get("POOLS", [{}])[0]
        manager_id = config.get("SLACK_MANAGER_ID", "")

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

        mock = not bool(config.get("SLACK_WEBHOOK_URL"))
        if config.get("SEND_DAILY_SUMMARY", True):
            blocks = build_daily_summary(
                men_games, women_games, top_men, top_women,
                men_url=pool.get("MEN_URL"),
                women_url=pool.get("WOMEN_URL"),
                top_n=config.get("TOP_N", 5)
            )
            post_message(config, blocks=blocks, mock=mock)

        seen = set(load_json(SEEN_FILE, []))
        seen.update(g["id"] for g in men_games + women_games)
        save_json(SEEN_FILE, list(seen))

    if not yearly_flag.get("LIVE_FOR_YEAR"):
        manager_id = config.get("SLACK_MANAGER_ID", "")
        yearly_reminder(config, manager_id)

    last_post = load_json(LAST_POST_FILE, {})
    if needs_config_reminder(config, last_post):
        print("[REMIND] Config incomplete — please finish setup.")

    print("[INFO] Done.")


if __name__ == "__main__":
    print("[INFO] March Madness Bot starting...")

    if len(sys.argv) > 1 and sys.argv[1].lower() == "stop":
        config = load_json(CONFIG_FILE, {})
        handle_stop(config)
        sys.exit(0)

    run()