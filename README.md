# March Madness Bot

This bot tracks NCAA March Madness brackets (men and women) and posts updates to Slack. It also posts a daily summary of results and top players.

## 🔧 How to Run

1. **Install dependencies**

```bash
pip install requests playwright
playwright install

2. **Create config.json**
Example:

3. **Run the Bot**
python march_madness_bot.py

4. **Slack Modes**
•	MOCK_SLACK = true → messages printed to console
•	LEADERBOARD_SOURCE = cbs → fetch top N from CBS
•	LEADERBOARD_SOURCE = manual → uses MANUAL_TOP from config
•	Fallback: If CBS scraping fails, the bot DMs the manager and waits for a manual top N response.

🆘 Manager Notification & Manual Top N Handling

If the bot cannot scrape the top N leaderboard:
	1.	Sends a Slack DM to the manager (BOT_MANAGER_SLACK_ID) asking for the top N.
	•	Includes bracket URLs if available.
	2.	Manager replies with top N in plain text:
            Player1 (score)
            Player2 (score)
            Player3 (score)
    3.	Bot parses the manager’s response and uses it for posts and summaries.

Purpose: Ensures the bot never posts empty or invalid leaderboard data.

⸻

Implementation Notes
	•	post_message_dm(user_id, text) → helper to send a Slack DM.
	•	wait_for_manager_response(user_id, n) → blocks until the manager responds with valid top N format.
	•	This logic integrates with get_top_n_wrapper to fallback to manual input if scraping fails.

## Configuration

Create a `config.json` file in the project root:

```json
{
  "SLACK_WEBHOOK_URL": "YOUR_SLACK_WEBHOOK_URL_HERE",
  "CBS_MEN_BRACKET_URL": "MEN_BRACKET_CBS_URL",
  "CBS_WOMEN_BRACKET_URL": "WOMEN_BRACKET_CBS_URL",
  "MOCK_SLACK": true,
  "TEST_DAILY_SUMMARY": true,
  "MINUTES_BETWEEN_MESSAGES": 30,
  "TOP_N": 3,
  "PLAYWRIGHT_HEADLESS": false
}

## Key Configuration Options

| Key | Description | Default |
|-----|-------------|---------|
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL | Required |
| `CBS_MEN_BRACKET_URL` | CBS men’s bracket pool URL | Required |
| `CBS_WOMEN_BRACKET_URL` | CBS women’s bracket pool URL | Required |
| `MOCK_SLACK` | If `true`, messages are printed instead of sent to Slack | `true` |
| `TEST_DAILY_SUMMARY` | If `true`, triggers a test daily summary on next run | `false` |
| `MINUTES_BETWEEN_MESSAGES` | Minimum minutes between Slack updates | `30` |
| `TOP_N` | Number of top players to pull from CBS brackets | `3` |
| `PLAYWRIGHT_HEADLESS` | Run Playwright browser headless | `false` |

## Usage

# Activate your virtualenv
source venv/bin/activate

# Run the bot
python3 main.py

	•	If MOCK_SLACK is true, messages are printed to console for testing.
	•	Daily summaries are sent automatically after 8 AM or when TEST_DAILY_SUMMARY is true.
	•	The bot automatically tracks seen games and only posts new results.

# Playwright Notes
	•	Store your CBS login session in playwright_state.json.
	•	For initial login or re-login (especially for women’s bracket), run Playwright in non-headless mode:

    from playwright.sync_api import sync_playwright


# March Madness Bot - Script Overview

## 📦 Script Structure

### 1️⃣ Imports & Config
- `requests`, `json`, `datetime`, `time`, `random`, `pathlib`, `playwright.sync_api`
- Loads `config.json` with:
  - CBS bracket URLs
  - Slack webhook
  - Mock flags
  - Message timing
  - Top N leaderboard count
  - Playwright headless/session settings
- State files:
  - `seen_games.json`
  - `last_post.json`
  - `last_rankings.json`

**Purpose:** Central configuration and persistent state storage.

---

### 2️⃣ State Helpers
- `load_json(path, default)` → safely load state
- `save_json(path, data)` → safely save state
- Loads `seen` games and `last_post` timestamp

**Purpose:** Track what has been posted and daily summaries.

---

### 3️⃣ Slack Helpers
- `post_message(text=None, blocks=None)`
  - Sends message to Slack via webhook
  - Prints to console if `MOCK` mode is enabled

**Purpose:** Centralized Slack posting, supporting both real and mock modes.

---

### 4️⃣ CBS Data Helpers
- `extract_seed(team)` → Extracts team seed from CBS JSON
- `get_final_games(url, gender)` → Scrapes all **final games** from CBS bracket JSON

**Purpose:** Core scraper for live game results.

---

### 5️⃣ Playwright Helpers
- `ensure_logged_in(cbs_url)` → Handles CBS login session
  - Opens browser if no session found
  - Saves session to `playwright_state.json`
- `get_top_n(cbs_url, n=TOP_N)` → Scrapes top N leaderboard using Playwright
- `get_top_n_wrapper(url, n)` → Wrapper for `cbs`, `manual`, or `mock` leaderboard

**Purpose:** Handles login, leaderboard scraping, and supports manual/mock modes.

---

### 6️⃣ Slack Message Builders
- `build_slack_message(game, top_men, top_women)` → Creates blocks for a single game
  - Detects upsets → adds ⚡🔥 emoji
  - Includes top N players
- `build_daily_summary(men_games, women_games, top_men, top_women)` → Daily summary blocks
  - Funny rankings → shows movement vs previous day
  - Lists all yesterday’s games with upset detection

**Purpose:** Converts scraped data into nicely formatted Slack messages.

---

### 7️⃣ Tournament Helpers
- `tournament_finished(men_games, women_games)` → Returns `True` if no games left

**Purpose:** Determines when to post final tournament message.

---

### 8️⃣ MAIN SCRIPT FLOW
1. Print bot start message
2. Scrape **today’s final games**: `men_games_today` & `women_games_today`
3. Scrape **top N leaderboard**: `men_top` & `women_top`
4. Combine games → `all_games`

**A. Post finished games**
- Only if `MINUTES_BETWEEN_MESSAGES` has passed
- Skips games already seen
- Calls `build_slack_message()` → `post_message()`
- Adds game IDs to `seen`

**B. Post daily summary**
- Triggered if after 8 AM and not posted yet today, or `TEST_DAILY_SUMMARY`
- Calls `build_daily_summary()` → `post_message()`
- Updates `last_post["daily_summary_date"]`

**C. Final tournament update**
- If no games left and `"final_update_posted"` not in `seen`:
  - Posts final leaderboard for men & women
  - Marks `"final_update_posted"` in `seen`

**D. Save state**
- `save_json(SEEN_FILE, list(seen))`
- `save_json(LAST_POST_FILE, last_post)`

---

### 9️⃣ Features Summary
- ✅ Handles both men’s and women’s brackets
- ✅ Detects upsets and adds emojis
- ✅ Posts individual game updates and daily summaries
- ✅ Tracks leaderboard movement with fun commentary
- ✅ Supports mock, manual, and real CBS leaderboard modes
- ✅ Playwright login handling with saved session
- ✅ Detects tournament end and posts final results