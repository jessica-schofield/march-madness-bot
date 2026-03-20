import requests
import json
import datetime
import time
import random
from pathlib import Path

# ------------------------------
# Load config
# ------------------------------
CONFIG_FILE = Path("config.json")
if not CONFIG_FILE.exists():
    raise FileNotFoundError("config.json not found! Please create it.")

with open(CONFIG_FILE) as f:
    config = json.load(f)

MEN_URL = config.get("men_bracket_url")
WOMEN_URL = config.get("women_bracket_url")
SLACK_WEBHOOK = config.get("slack_webhook_url")
MOCK = config.get("mock_slack", True)
TEST_DAILY_SUMMARY = config.get("test_daily_summary", False)

# ------------------------------
# State files
# ------------------------------
SEEN_FILE = Path("seen_games.json")
LAST_POST_FILE = Path("last_post.json")
LAST_RANKINGS_FILE = Path("last_rankings.json")

# ------------------------------
# Helpers for state management
# ------------------------------
def load_json(path, default):
    if path.exists():
        try:
            return json.load(path.open())
        except:
            return default
    return default

def save_json(path, data):
    with path.open("w") as f:
        json.dump(data, f)

seen = set(load_json(SEEN_FILE, []))
last_post = load_json(LAST_POST_FILE, {"timestamp": 0, "daily_summary_date": None})

# ------------------------------
# Slack helper
# ------------------------------
def post_message(text):
    if MOCK:
        print(f"[SLACK MOCK] {text}\n{'-'*50}")
    else:
        requests.post(SLACK_WEBHOOK, json={"text": text})

# ------------------------------
# Seed extraction helper
# ------------------------------
def extract_seed(team):
    rank = team.get("curatedRank", 0)
    if isinstance(rank, dict):
        return int(rank.get("current", 0))
    try:
        return int(rank)
    except:
        return 0

# ------------------------------
# Generic bracket scraper
# ------------------------------
def get_final_games(url, gender):
    if not url:
        return []
    try:
        data = requests.get(url).json()
    except:
        return []

    games = data.get("events", [])
    finals = []

    for game in games:
        try:
            competition = game["competitions"][0]
            status = competition["status"]["type"]["name"]
            game_id = game["id"]

            if status != "STATUS_FINAL":
                continue

            teams = competition["competitors"]
            home = next(t for t in teams if t["homeAway"] == "home")
            away = next(t for t in teams if t["homeAway"] == "away")

            finals.append({
                "id": game_id,
                "gender": gender,
                "home": home["team"]["displayName"],
                "home_score": home["score"],
                "home_seed": extract_seed(home),
                "away": away["team"]["displayName"],
                "away_score": away["score"],
                "away_seed": extract_seed(away),
                "date": game.get("date")
            })
        except:
            continue
    return finals

# ------------------------------
# Slack message builders
# ------------------------------
def build_slack_message(game, top_three_men, top_three_women):
    home_score = int(game['home_score'])
    away_score = int(game['away_score'])
    home_seed = game.get('home_seed', 0)
    away_seed = game.get('away_seed', 0)

    upset_emoji = ""
    if (home_score > away_score and home_seed > away_seed) or \
       (away_score > home_score and away_seed > home_seed):
        upset_emoji = "⚡🔥"

    bracket_emoji = "🏆" if game['gender'] == 'men' else "👑"

    message = (
        f"{bracket_emoji} {upset_emoji} FINAL: {game['away']} {away_score} - {home_score} {game['home']} {upset_emoji}\n\n"
        f"📊 *Men’s Top 3:* \n" + "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(top_three_men)) + "\n\n"
        f"👩‍🦰 *Women’s Top 3:* \n" + "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(top_three_women))
    )
    return message

def build_daily_summary(men_games, women_games, top_three_men, top_three_women):
    today_str = datetime.date.today().strftime("%B %d")
    last_rankings = load_json(LAST_RANKINGS_FILE, {})
    last_men = last_rankings.get("men", [])
    last_women = last_rankings.get("women", [])

    intros = [
        "☀️ Good morning! Here’s the madness from yesterday:",
        "🎉 Daily chaos report incoming!",
        "😂 Buckle up: yesterday in March Madness...",
        "☕ Grab your coffee, here’s what happened on the court yesterday:",
        "🏀 Another day, another bracket disaster report:"
    ]
    intro = random.choice(intros)
    summary = f"{intro}\n\n"

    if men_games:
        summary += "🏀 *Men’s Games:* \n"
        for g in men_games:
            summary += f"- {g['away']} {g['away_score']} - {g['home_score']} {g['home']}\n"
    else:
        summary += "🏀 No men’s games yesterday. 😴\n"

    if women_games:
        summary += "\n👑 *Women’s Games:* \n"
        for g in women_games:
            summary += f"- {g['away']} {g['away_score']} - {g['home_score']} {g['home']}\n"
    else:
        summary += "\n👩‍🦰 No women’s games yesterday. 🤫\n"

    # Fixed quip function
    def make_funny_rankings(top_list, last_list):
        lines = []
        for i, entry in enumerate(top_list):
            if entry in last_list:
                move = last_list.index(entry) - i
                if move > 0:
                    poke = f"⬆️ +{move} Gaining on everyone!"
                elif move < 0:
                    poke = f"⬇️ {abs(move)} Ouch, dropping spots!"
                else:
                    poke = "✅ Holding steady at this spot!"
            else:
                poke = "✨ New entrant to top 3!"
            lines.append(f"{i+1}. {entry} — {poke}")
        return lines

    summary += "\n📊 *Men’s Top 3:* \n" + "\n".join(make_funny_rankings(top_three_men, last_men))
    summary += "\n\n👩‍🦰 *Women’s Top 3:* \n" + "\n".join(make_funny_rankings(top_three_women, last_women))
    summary += "\n\n😂 Remember: brackets are like office politics — unpredictable, dramatic, and slightly embarrassing!"

    # Save current top rankings for next comparison
    save_json(LAST_RANKINGS_FILE, {"men": top_three_men, "women": top_three_women})

    return summary

# ------------------------------
# Tournament finished check
# ------------------------------
def tournament_finished(men_games, women_games):
    return len(men_games) == 0 and len(women_games) == 0

# ------------------------------
# MAIN
# ------------------------------
if __name__ == "__main__":
    print("[INFO] March Madness Bot starting...")
    if MOCK:
        print("[INFO] MOCK SLACK mode active — messages will be printed only.\n" + "-"*50)

    now_ts = time.time()
    men_games_today = get_final_games(MEN_URL, 'men')
    women_games_today = get_final_games(WOMEN_URL, 'women')

    # Placeholder top 3
    men_top_three = ["Alice", "Bob", "Charlie"] if MEN_URL else []
    women_top_three = ["Dana", "Eve", "Faith"] if WOMEN_URL else []

    all_games = men_games_today + women_games_today

    # -------------------
    # Post finished games (30 min rate limit)
    # -------------------
    if now_ts - last_post.get("timestamp", 0) > 30*60:
        for g in all_games:
            if g["id"] in seen:
                continue
            message = build_slack_message(g, men_top_three, women_top_three)
            post_message(message)
            seen.add(g["id"])
        last_post["timestamp"] = now_ts

    # -------------------
    # Daily summary (8AM or test mode)
    # -------------------
    today = datetime.date.today()
    should_post_daily = False

    # Normal daily summary check (after 8AM)
    if datetime.datetime.now().hour >= 8 and last_post.get("daily_summary_date") != str(today):
        should_post_daily = True

    # Force test summary if test flag is on
    if TEST_DAILY_SUMMARY:
        should_post_daily = True  # ✅ force it
        config["test_daily_summary"] = False  # reset the flag so it doesn't repeat
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print("[INFO] TEST DAILY SUMMARY triggered!")  # Add this line so you see it

    if datetime.datetime.now().hour >= 8 and last_post.get("daily_summary_date") != str(today):
        should_post_daily = True

    if TEST_DAILY_SUMMARY:
        should_post_daily = True
        config["test_daily_summary"] = False
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    if should_post_daily:
        daily_message = build_daily_summary(men_games_today, women_games_today, men_top_three, women_top_three)
        post_message(daily_message)
        last_post["daily_summary_date"] = str(today)

    # -------------------
    # Final tournament update
    # -------------------
    if tournament_finished(men_games_today, women_games_today) and "final_update_posted" not in seen:
        final_message = "🏆🎉 THE TOURNAMENT IS OVER! 🎉🏆\n\n"
        if men_top_three:
            final_message += "📊 *Final Men’s Top 3:* \n" + "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(men_top_three)) + "\n\n"
        if women_top_three:
            final_message += "👩‍🦰 *Final Women’s Top 3:* \n" + "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(women_top_three))
        post_message(final_message)
        seen.add("final_update_posted")

    # -------------------
    # Save state
    # -------------------
    save_json(SEEN_FILE, list(seen))
    save_json(LAST_POST_FILE, last_post)