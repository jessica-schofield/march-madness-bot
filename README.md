# 🏀 March Madness Slack Bot

Automatically posts March Madness game updates, leaderboard standings, and daily summaries to your Slack workspace. Works with CBS Sports bracket pools for both men's and women's tournaments.

---

## 🌟 Features

- Scrapes CBS Sports brackets for men's and women's tournaments
- Tracks final game scores and identifies upsets ⚡🔥
- Sends daily summary messages to Slack with top players and leaderboard movers
- Fully testable without posting to Slack (mock mode)
- Remembers previously posted games to avoid duplicates
- Configurable for weekend posting, message frequency, and more

---

## 🚀 Getting Started (No Experience Needed!)

Don't worry if you've never used a terminal before — these instructions walk you through every step.

### Step 1 — Open Terminal

**On Mac:**
1. Press `Command (⌘) + Space` to open Spotlight Search
2. Type `Terminal` and press `Enter`
3. A black or white window with a blinking cursor will open — that's the terminal!

**On Windows:**
1. Press the `Windows` key
2. Type `PowerShell` and press `Enter`

> 💡 **What is the terminal?** It's a way to give your computer text instructions. You'll type a command and press `Enter` to run it.

---

### Step 2 — Install Python (if you don't have it)

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Click the big yellow **Download Python** button
3. Open the downloaded file and follow the installer
4. ✅ On Mac: make sure to check **"Add Python to PATH"** during installation

To check it worked, type this in your terminal and press `Enter`:
```bash
python3 --version
```
You should see something like `Python 3.11.0`. If you do, you're good!

---

### Step 3 — Download the Bot

If you have Git installed:
```bash
git clone https://github.com/jessica-schofield/march-madness-bot.git
cd march-madness-bot
```

Or download the ZIP file from GitHub:
1. Click the green **Code** button on the GitHub page
2. Click **Download ZIP**
3. Unzip the file somewhere easy to find (like your Desktop)
4. In your terminal, navigate to the folder:
```bash
cd ~/Desktop/march-madness-bot
```

> 💡 **`cd` means "change directory"** — it's like double-clicking a folder.

---

### Step 4 — Set Up the Bot Environment

Copy and paste each of these commands into your terminal, pressing `Enter` after each one:

**Create a virtual environment** (a safe, isolated space for the bot):
```bash
python3 -m venv venv
```

**Activate it:**
```bash
# Mac/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

You'll know it worked when you see `(venv)` at the start of your terminal line.

**Install dependencies** (the tools the bot needs):
```bash
pip install -r requirements.txt
```

**Install Playwright browsers** (used to read CBS Sports):
```bash
playwright install
```

---

### Step 5 — Run Setup

```bash
python3 main.py
```

The bot will walk you through setup interactively — it will ask you questions and you just type your answers. You'll be asked for:

- How many top players to highlight (e.g. `5`)
- Your CBS Sports pool URLs (men's and women's)
- How often to post messages (in minutes)
- Whether to post on weekends
- Your Slack webhook URL (optional — see below)

> 💡 You can always re-run `python3 main.py` to change your settings.

---

### Step 6 — Set Up Slack (Optional)

To post to a real Slack channel, you need a **Webhook URL**. Here's how to get one:

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and sign in
2. Click **Create New App** → **From scratch**
3. Give it a name (e.g. `March Madness Bot`) and choose your workspace
4. In the left sidebar, click **Incoming Webhooks**
5. Toggle **Activate Incoming Webhooks** to ON
6. Click **Add New Webhook to Workspace**
7. Choose the channel you want it to post in and click **Allow**
8. Copy the webhook URL that appears (it starts with `https://hooks.slack.com/...`)
9. Paste it when the bot asks for your Slack Webhook URL during setup

> 💡 If you skip this, the bot will run in **mock mode** — messages print to your terminal instead of posting to Slack. Great for testing!

---

### Step 7 — Find Your CBS Pool URLs

1. Log in to [CBS Sports](https://picks.cbssports.com)
2. Navigate to your bracket pool
3. Click on the **Standings** tab
4. Copy the URL from your browser's address bar
5. Paste it when setup asks for your pool URL

You'll need one URL for the **men's pool** and one for the **women's pool** (or just one if you only have one).

---

### Step 8 — Run the Bot!

```bash
python3 main.py
```

That's it! The bot will scrape scores, build messages, and post to Slack (or print them if in mock mode).

---

## 🔁 Running the Bot Daily

To keep the bot running automatically, you can schedule it. On Mac, the easiest way is `cron`:

```bash
crontab -e
```

Add this line to run it every 30 minutes:
```
*/30 * * * * cd /path/to/march-madness-bot && venv/bin/python3 main.py
```

Replace `/path/to/march-madness-bot` with the actual path to your folder.

---

## ⚙️ Configuration Reference

All settings are saved in `config.json` after setup. You can edit this file directly in any text editor.

```json
{
  "TOP_N": 5,
  "MINUTES_BETWEEN_MESSAGES": 30,
  "PLAYWRIGHT_HEADLESS": true,
  "PLAYWRIGHT_STATE": "playwright_state.json",
  "POST_ON_WEEKENDS": false,
  "POOLS": [
    {
      "NAME": "My CBS Pool",
      "SOURCE": "cbs",
      "MEN_URL": "https://picks.cbssports.com/.../standings",
      "WOMEN_URL": "https://picks.cbssports.com/.../standings"
    }
  ],
  "MANUAL_TOP": [],
  "SLACK_WEBHOOK_URL": "https://hooks.slack.com/...",
  "SLACK_MANAGER_ID": "",
  "MOCK_SLACK": false
}
```

| Key | What it does | Example |
|-----|-------------|---------|
| `TOP_N` | How many top players to show | `5` |
| `MINUTES_BETWEEN_MESSAGES` | How often to post game updates | `30` |
| `PLAYWRIGHT_HEADLESS` | Hide the browser window when scraping | `true` |
| `POST_ON_WEEKENDS` | Post on Saturdays and Sundays | `false` |
| `POOLS` | Your CBS pool URLs | See above |
| `MANUAL_TOP` | Fallback player list if scraping fails | `["Alice (100)", "Bob (95)"]` |
| `SLACK_WEBHOOK_URL` | Where to post Slack messages | `https://hooks.slack.com/...` |
| `SLACK_MANAGER_ID` | Your Slack user ID for DM fallback | `U012AB3CD` |
| `MOCK_SLACK` | Print messages instead of posting | `true` |

---

## ❓ FAQ

**Q: Messages aren't posting to Slack.**
- Check that `SLACK_WEBHOOK_URL` is set in `config.json`
- Make sure `MOCK_SLACK` is `false`

**Q: CBS scraping fails.**
- The bot will ask you to enter the top players manually
- Make sure you're logged into CBS Sports — run setup again to refresh the session

**Q: How do I update the top players list?**
- Edit `MANUAL_TOP` in `config.json`, or run `python3 main.py` again

**Q: I see `(venv)` disappeared — did something break?**
- No! Just re-activate: `source venv/bin/activate` (Mac) or `venv\Scripts\activate` (Windows)

**Q: What if I get a `python3: command not found` error?**
- Try `python` instead of `python3`
- Or reinstall Python from [python.org](https://www.python.org/downloads/) and make sure to check "Add to PATH"

---

## 📁 File Reference

| File | What it is |
|------|-----------|
| `main.py` | Runs the bot |
| `bot_setup.py` | Interactive setup wizard |
| `messages.py` | Builds Slack messages |
| `slack_utils.py` | Posts to Slack |
| `slack_dm.py` | Handles Slack DM interactions |
| `config.py` | Loads and saves configuration |
| `cbs.py` | Scrapes CBS Sports data |
| `config.json` | Your settings (not saved to Git) |
| `seen_games.json` | Tracks posted games |
| `last_rankings.json` | Tracks previous leaderboard for movers |
| `requirements.txt` | Python packages needed |

---

## 📝 Notes

- Python 3.9 or higher is required
- On Mac, Playwright may show a warning about OpenSSL — this is harmless
- `config.json` is excluded from Git so your Slack credentials stay private
- Run the bot at least once to save your CBS login session

---

## 📄 License