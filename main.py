#!/usr/bin/env python3
# ------------------------------
# MARCH MADNESS SLACK BOT
# ------------------------------

import requests
import json
import datetime
import time
from pathlib import Path
from slack_sdk import WebClient
from yearly_setup_reminder import yearly_reminder, load_flag
import slack_setup
import asyncio
from playwright.async_api import async_playwright

# ------------------------------
# Config & paths
# ------------------------------
CONFIG_FILE = Path("config.json")
SEEN_FILE = Path("seen_games.json")
LAST_POST_FILE = Path("last_post.json")
LAST_RANKINGS_FILE = Path("last_rankings.json")

# ------------------------------
# Helper functions
# ------------------------------
def get_input(prompt, default=None, required=False):
    while True:
        val = input(f"{prompt} " + (f"[Default: {default}]: " if default else ": "))
        if not val and default is not None:
            return default
        if val:
            return val
        if required:
            print("This field is required. Please enter a value.")

def load_json(path, default):
    if path.exists():
        try:
            return json.load(path.open())
        except:
            return default
    return default

def save_json(path, data):
    with path.open("w") as f:
        json.dump(data, f, indent=2)

# ------------------------------
# CBS / Playwright helpers (async)
# ------------------------------
PLAYWRIGHT_STATE = Path("playwright_state.json")
PLAYWRIGHT_HEADLESS = True

def playwright_state_empty(path):
    return not path.exists() or path.stat().st_size == 0

async def ensure_logged_in_async(cbs_url):
    if PLAYWRIGHT_STATE.exists():
        print("[INFO] Existing Playwright session found.")
        return
    print("[SETUP REQUIRED] No CBS login session found. Browser will open for interactive login.\n")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(cbs_url)
        print("[ACTION] Please log in to CBS manually in the browser window.")
        await page.wait_for_selector("table", timeout=300_000)
        await context.storage_state(path=str(PLAYWRIGHT_STATE))
        await browser.close()
    print("[INFO] CBS login session saved!\n")

async def get_top_n_async(cbs_url, n=3):
    top_list = []
    if playwright_state_empty(PLAYWRIGHT_STATE):
        await ensure_logged_in_async(cbs_url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            context = await browser.new_context(storage_state=str(PLAYWRIGHT_STATE))
            page = await context.new_page()
            await page.goto(cbs_url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_selector("table", timeout=15_000)
            tables = await page.query_selector_all("table")
            if len(tables) < 2:
                print("[WARN] Leaderboard table not found, retrying login...")
                await browser.close()
                if PLAYWRIGHT_STATE.exists(): PLAYWRIGHT_STATE.unlink()
                return await get_top_n_async(cbs_url, n)
            leaderboard_table = tables[1]
            rows = await leaderboard_table.query_selector_all("tr")
            for row in rows[1:n+1]:
                cells = await row.query_selector_all("td")
                if len(cells) >= 4:
                    name = (await cells[2].inner_text()).strip()
                    points = (await cells[3].inner_text()).strip()
                    top_list.append(f"{name} ({points})")
            await browser.close()
    except Exception as e:
        print(f"[ERROR] Failed to scrape CBS top {n}: {e}")
    return top_list

# Sync wrapper
def get_top_n(cbs_url, n=3):
    return asyncio.run(get_top_n_async(cbs_url, n))

# ------------------------------
# CBS data parsing
# ------------------------------
def extract_seed(team):
    rank = team.get("curatedRank", 0)
    if isinstance(rank, dict):
        return int(rank.get("current", 0))
    try:
        return int(rank)
    except:
        return 0

def get_final_games(url, gender):
    if not url: return []
    try:
        data = requests.get(url).json()
    except:
        return []
    games = []
    for game in data.get("events", []):
        try:
            comp = game["competitions"][0]
            if comp["status"]["type"]["name"] != "STATUS_FINAL": continue
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            games.append({
                "id": game["id"],
                "gender": gender,
                "home": teams["home"]["team"]["displayName"],
                "home_score": teams["home"]["score"],
                "home_seed": extract_seed(teams["home"]),
                "away": teams["away"]["team"]["displayName"],
                "away_score": teams["away"]["score"],
                "away_seed": extract_seed(teams["away"]),
                "date": game.get("date")
            })
        except:
            continue
    return games

# ------------------------------
# Build daily summary
# ------------------------------
def build_daily_summary(men_games, women_games, top_men, top_women):
    last_rankings = load_json(LAST_RANKINGS_FILE, {"men":[], "women":[]})

    def calculate_movers(new, old):
        old_positions = {name.split(" (")[0]: idx for idx, name in enumerate(old)}
        movers = []
        for idx, entry in enumerate(new):
            name = entry.split(" (")[0]
            old_idx = old_positions.get(name, idx)
            change = old_idx - idx
            movers.append((name, change))
        gained = sorted([m for m in movers if m[1] > 0], key=lambda x: -x[1])
        lost = sorted([m for m in movers if m[1] < 0], key=lambda x: x[1])
        return gained, lost

    men_gained, men_lost = calculate_movers(top_men, last_rankings.get("men", []))
    women_gained, women_lost = calculate_movers(top_women, last_rankings.get("women", []))

    blocks = slack_setup.build_daily_summary_blocks(
        men_games, women_games, top_men, top_women,
        extra_summary={
            "men_gained": men_gained[:3],
            "men_lost": men_lost[:3],
            "women_gained": women_gained[:3],
            "women_lost": women_lost[:3],
        }
    )

    save_json(LAST_RANKINGS_FILE, {"men": top_men, "women": top_women})
    return blocks

# ------------------------------
# Post message
# ------------------------------
def post_message(text=None, blocks=None):
    today = datetime.datetime.now().weekday()
    if not config.get("POST_ON_WEEKENDS", True) and today >= 5:
        print("[INFO] Skipping posting today — weekend posting disabled")
        return

    if MOCK:
        print("[SLACK MOCK]")
        if blocks:
            for b in blocks: print(b)
        elif text:
            print(text)
        print("-"*50)
    else:
        payload = {"text": text} if text else {}
        if blocks: payload["blocks"] = blocks
        requests.post(SLACK_WEBHOOK, json=payload)

# ------------------------------
# Setup flow (CLI vs Slack)
# ------------------------------
def first_time_setup_prompt():
    choice = get_input("Do you want to configure via Slack or Command Line? (slack/cli)", default="cli").lower()
    return choice

def run_first_time_setup():
    config={} if not CONFIG_FILE.exists() else load_json(CONFIG_FILE,{})
    choice = first_time_setup_prompt()
    if choice=="cli":
        config = command_line_setup(config)
        config = slack_setup_flow(config)
    else:
        config = slack_setup_flow(config)
        config = command_line_setup(config)
    return config

def command_line_setup(config):
    global PLAYWRIGHT_HEADLESS, PLAYWRIGHT_STATE
    print("\n=== COMMAND LINE SETUP ===\n")

    config["TOP_N"] = int(get_input("Top users to brag about each day?", default=str(config.get("TOP_N",3))))
    config["MINUTES_BETWEEN_MESSAGES"] = int(get_input("Minutes between automated messages?", default=str(config.get("MINUTES_BETWEEN_MESSAGES",30))))
    config["PLAYWRIGHT_HEADLESS"] = config.get("PLAYWRIGHT_HEADLESS", True)
    config["PLAYWRIGHT_STATE"] = config.get("PLAYWRIGHT_STATE", "playwright_state.json")
    PLAYWRIGHT_HEADLESS = config["PLAYWRIGHT_HEADLESS"]
    PLAYWRIGHT_STATE = Path(config["PLAYWRIGHT_STATE"])

    config["POST_ON_WEEKENDS"] = get_input(
        "Post game updates and daily summaries on weekends? (YES/NO)", default="YES"
    ).strip().upper() == "YES"

    men_url = get_input("CBS Men’s Pool URL (blank if none)", default=config.get("POOLS",[{}])[0].get("MEN_URL",""))
    women_url = get_input("CBS Women’s Pool URL (blank if none)", default=config.get("POOLS",[{}])[0].get("WOMEN_URL",""))

    config["POOLS"] = []
    if men_url or women_url:
        pool = {"NAME":"Main CBS Pool","SOURCE":"cbs"}
        if men_url: pool["MEN_URL"] = men_url
        if women_url: pool["WOMEN_URL"] = women_url
        config["POOLS"].append(pool)

    # Scrape top N users for each pool and gender
    config["MANUAL_TOP"] = []
    for pool in config.get("POOLS", []):
        for gender_key in ["MEN_URL","WOMEN_URL"]:
            url = pool.get(gender_key)
            if url:
                config["MANUAL_TOP"] += get_top_n(url, config["TOP_N"])

    # Fallback test users
    while len(config["MANUAL_TOP"]) < config["TOP_N"]*2:
        i = len(config["MANUAL_TOP"])
        config["MANUAL_TOP"].append(f"TestUser{i+1} ({100-i})")

    config["SLACK_WEBHOOK_URL"] = config.get("SLACK_WEBHOOK_URL","")
    config["SLACK_MANAGER_ID"] = config.get("SLACK_MANAGER_ID","")
    config["MOCK_SLACK"] = True if not config["SLACK_WEBHOOK_URL"] else False

    save_json(CONFIG_FILE, config)

    run_sim = get_input("Run full test simulation now? (YES/NO)", default="YES").strip().upper()
    if run_sim == "YES":
        global MOCK
        MOCK = True
        run_quick_test(config)

    return config

def slack_setup_flow(config):
    choice=get_input("Configure Slack now? (YES/NO)", default="YES").strip().upper()
    if choice!="YES": return config
    slack_id=get_input("Enter your Slack ID for DM fallback", required=True)
    config["SLACK_MANAGER_ID"]=slack_id
    config["MOCK_SLACK"]=False if config.get("SLACK_WEBHOOK_URL") else True
    slack_setup.run_setup(WebClient(token="SIMULATE_TOKEN"), slack_id)
    save_json(CONFIG_FILE, config)
    return config

# ------------------------------
# QUICK TEST RUN
# ------------------------------
def run_quick_test(config):
    men_games = get_final_games(config.get("POOLS",[{}])[0].get("MEN_URL",""), "men") or [{
        "id":"MEN_TEST_001","gender":"men","home":"Duke","home_score":82,"home_seed":2,"away":"UNC","away_score":78,"away_seed":7}]
    women_games = get_final_games(config.get("POOLS",[{}])[0].get("WOMEN_URL",""), "women") or [{
        "id":"WOMEN_TEST_001","gender":"women","home":"UConn","home_score":75,"home_seed":1,"away":"Stanford","away_score":70,"away_seed":4}]

    top_n = config.get("TOP_N",3)
    top_men = config.get("MANUAL_TOP",[])[:top_n]
    top_women = config.get("MANUAL_TOP",[])[top_n:top_n*2]

    print("\n[TEST] Men’s game message:")
    for b in slack_setup.build_slack_message(men_games[0], top_men, top_women):
        print(b)

    print("\n[TEST] Women’s game message:")
    for b in slack_setup.build_slack_message(women_games[0], top_men, top_women):
        print(b)

    print("\n[TEST] Daily summary with movers:")
    for b in build_daily_summary(men_games, women_games, top_men, top_women):
        print(b)

    print("\n=== END TEST SIMULATION ===\n")

# ------------------------------
# MAIN EXECUTION
# ------------------------------
if __name__=="__main__":
    print("[INFO] March Madness Bot starting...")
    REQUIRED_KEYS={"TOP_N":3,"MINUTES_BETWEEN_MESSAGES":30,"PLAYWRIGHT_HEADLESS":True,
                   "PLAYWRIGHT_STATE":"playwright_state.json","POOLS":[],"SLACK_WEBHOOK_URL":"",
                   "SLACK_MANAGER_ID":""}

    def needs_setup(cfg): return any(k not in cfg or cfg[k] in (None,"",[]) for k in REQUIRED_KEYS)

    config={} if not CONFIG_FILE.exists() else load_json(CONFIG_FILE,{})
    if not CONFIG_FILE.exists() or needs_setup(config):
        config=run_first_time_setup()

    cbs_pool=next((p for p in config.get("POOLS",[]) if p.get("SOURCE")=="cbs"),None)
    MEN_URL=cbs_pool.get("MEN_URL") if cbs_pool else None
    WOMEN_URL=cbs_pool.get("WOMEN_URL") if cbs_pool else None
    SLACK_WEBHOOK=config.get("SLACK_WEBHOOK_URL")
    MOCK=config.get("MOCK_SLACK",True)
    MINUTES_BETWEEN_MESSAGES=config.get("MINUTES_BETWEEN_MESSAGES",30)
    TOP_N=config.get("TOP_N",3)
    PLAYWRIGHT_HEADLESS=config.get("PLAYWRIGHT_HEADLESS",True)
    PLAYWRIGHT_STATE=Path(config.get("PLAYWRIGHT_STATE","playwright_state.json"))
    MANAGER_ID=config.get("SLACK_MANAGER_ID")
    seen=set(load_json(SEEN_FILE,[]))
    last_post=load_json(LAST_POST_FILE,{"timestamp":0,"daily_summary_date":None})

    if MANAGER_ID: yearly_reminder(WebClient(token="SIMULATE_TOKEN"),MANAGER_ID)
    yearly_flag=load_flag()
    LIVE_FOR_YEAR=yearly_flag.get("LIVE_FOR_YEAR",False)
    if not LIVE_FOR_YEAR:
        print("[INFO] Bot not live yet — forcing TEST MODE.\n")
        MOCK=True
    if MOCK:
        print("[INFO] MOCK SLACK mode active — messages will be printed only.\n" + "-"*50)
        run_quick_test(config)