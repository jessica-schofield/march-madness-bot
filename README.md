# March Madness Slack Bot

Automatically posts NCAA March Madness bracket updates to Slack. Supports:

- Men’s & women’s brackets (optional)
- Daily 8AM summary with humor, emojis, and biggest movers
- Upset detection ⚡🔥
- Final tournament celebration
- Configurable mock mode for testing before Slack approval
- Test daily summary mode

---

## Setup

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/march-madness-bot.git
cd march-madness-bot

### 2. Virtual Environment

python3 -m venv venv
source venv/bin/activate

### 3. Install Dependencies

pip install -r requirements.txt

### 4. config.json example 

{
  "men_bracket_url": "YOUR_MENS_BRACKET_URL",
  "women_bracket_url": "YOUR_WOMENS_BRACKET_URL",
  "slack_webhook_url": "YOUR_SLACK_WEBHOOK",
  "mock_slack": true,
  "test_daily_summary": true
}

	•	mock_slack: prints instead of posting
	•	test_daily_summary: forces daily summary to run once

### 5. Run

python3 main.py

### 6. Automate with Cron

*/5 * * * * cd /path/to/march-madness-bot && /path/to/venv/bin/python main.py >> cron.log 2>&1

### 7. Custom bracket sources

If you use a non-CBS/ESPN source, create a function returning:

[{
    "id": "game1",
    "home": "Team A",
    "home_score": 70,
    "home_seed": 3,
    "away": "Team B",
    "away_score": 68,
    "away_seed": 6,
    "gender": "men"
}]

Plug it into main.py and it will integrate automatically.

⸻

### 8. Notes
	•	Bot is fully headless; no windows open
	•	Supports mock Slack mode for testing
	•	Daily summary, biggest movers, and final celebration included