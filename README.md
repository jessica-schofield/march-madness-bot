# 🏀 March Madness Bot

A Slack bot that tracks NCAA March Madness games and bracket standings, posting live game updates and daily summaries to your Slack workspace.

---

## What's New — v1.1.1

### 🐛 Placeholder URL Browser Skip Fix
The bot now correctly skips the browser login step when both pool URLs are still set to placeholder values. Previously, `ensure_cbs_login` could be called unnecessarily during setup — this is now handled gracefully with a clear `[WARN]` log message.

---

## What's New — v1.1

### 🆕 Personal Bracket Tracking via Slack DMs
The bot can now walk you through setup entirely over Slack DMs. After entering your webhook and user ID, the bot will:
- Ask all config questions (top N, game updates, daily summary, weekend posting) via DM
- Prompt you to paste your CBS, ESPN, or Yahoo bracket pool standings URLs
- Open a browser for login if needed, with retry and manual fallback options
- Show a preview of your daily message and ask for go-live confirmation

No more command-line-only setup — the full configuration flow now happens in your pocket.

---

## Features

- 🔴 **Live game updates** — posts to Slack the moment a game goes final
- ☀️ **Daily morning summaries** — recap of yesterday's games with current bracket standings
- 📊 **Leaderboard tracking** — scrapes CBS, ESPN, or Yahoo bracket pools for top N standings
- 💬 **Slack DM setup** — configure everything interactively via Slack DMs
- ⚡ **Upset detection** — flags upsets with ⚡🔥 in game messages
- 📅 **Weekend control** — optionally skip posting on weekends
- 🔁 **Retry logic** — browser login failures prompt for retry or manual entry

---

## Requirements

- Python 3.9+
- A Slack workspace with an incoming webhook URL
- Your Slack user ID (for DM-based setup)
- [Playwright](https://playwright.dev/python/) for bracket scraping

```sh
pip install -r requirements.txt
playwright install chromium
```

---

## Setup

```sh
python3 main.py
```

You'll be asked whether to set up via **Slack DMs** or **command line**. Either path will guide you through:

1. Slack webhook URL and your user ID
2. Leaderboard preferences (top N, update frequency)
3. Bracket pool URLs (CBS, ESPN, Yahoo, or custom)
4. Go-live confirmation

Config is saved to `config.json` and reused on subsequent runs.

---

## Running the Bot

The bot is designed to be invoked by cron. Each run it checks for new final games, scrapes the leaderboard, and posts to Slack if there is anything new to report — then exits.

**`main.py` does not loop or sleep.** Scheduling is handled entirely by cron.

### Crontab setup (one-time)

Only one cron entry is needed:

```cron
*/5 * * * * cd /path/to/march-madness-bot && /path/to/venv/bin/python main.py >> /path/to/march-madness-bot/cron.log 2>&1
```

Edit with `crontab -e`. Replace `/path/to/` with your actual install path.

**You never need to update the crontab again.** When both championships are final, the bot automatically:
- Posts a season wrap-up message to Slack
- Sets itself to sleep (`LIVE_FOR_YEAR = false`)
- Advances `TOURNAMENT_END_MEN` and `TOURNAMENT_END_WOMEN` in `config.json` by one year
- Schedules a March 10 reminder in crontab for next year

### Stopping the bot manually

```sh
python3 main.py stop
```

This sets the `LIVE_FOR_YEAR` flag to `False` so the bot skips posting until re-setup next year.

---

## Running

```sh
python3 main.py
```

The bot runs in a loop, checking for new final games on the configured interval and posting to Slack.

---

## Configuration

All settings are stored in `config.json`. Key fields:

| Key | Description | Default |
|---|---|---|
| `METHOD` | `cli` or `slack` | `slack` |
| `TOP_N` | Number of bracket leaders to show | `5` |
| `MINUTES_BETWEEN_MESSAGES` | Batch window for game updates (`0` = live) | `60` |
| `POST_WEEKENDS` | Post on Saturdays and Sundays | `false` |
| `SEND_GAME_UPDATES` | Post when games go final | `true` |
| `SEND_DAILY_SUMMARY` | Post morning recap | `true` |
| `TOURNAMENT_END_MEN` | Men's final date (YYYY-MM-DD) | `2026-04-07` |
| `TOURNAMENT_END_WOMEN` | Women's final date (YYYY-MM-DD) | `2026-04-06` |
| `SLACK_WEBHOOK_URL` | Incoming webhook URL | — |
| `SLACK_MANAGER_ID` | Your Slack user ID (e.g. `U012ABC`) | — |
| `POOLS` | List of bracket pool configs with `MEN_URL` / `WOMEN_URL` | — |

---

## Tests

```sh
pytest
```

337 tests covering setup, scraping, Slack utilities, message formatting, and import hygiene.

---

## Project Structure

```
march-madness-bot/
├── bot_setup/          # Setup flow, config helpers, CLI/DM prompts
├── scrapers/           # CBS scraper (Playwright-based)
├── slack_bot/          # Slack posting, DM handling, message builders
├── sources/            # ESPN + CBS data fetchers
├── status/             # Yearly flag, setup reminders, cron helpers
├── tests/              # Full test suite
└── main.py             # Entry point
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full release history.