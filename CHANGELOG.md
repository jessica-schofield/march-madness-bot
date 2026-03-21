# Changelog

All notable changes to this project will be documented in this file.

---

## [v1.1.1] — March 2026

### Added
- **Leaderboard 1.5x cap** — results returned by the scraper can never exceed `int(TOP_N * 1.5)` entries; prevents oversized leaderboards when multiple players share a rank at the boundary. Uses `int()` truncation (`TOP_N=3` → max 4, not 5). A `[INFO]` log is printed when results are trimmed.

### Fixed
- **Placeholder URL browser skip** — bot correctly skips `ensure_cbs_login` when both pool URLs are `example.com` placeholders; logs `[WARN] Both pool URLs are placeholders` and skips the browser block entirely
- **Empty URL browser skip** — browser login block is now bypassed entirely when both URLs are empty strings, rather than entering the block and silently no-oping

### Tests
- Expanded to **353 tests** (was 337)
- Rewrote `tests/test_integration.py` with a shared `_standard_patches()` context manager — eliminates ~80% of per-test boilerplate
- Split browser-skip coverage into three distinct cases: empty URLs, `example.com` placeholders, and valid session on disk
- Added `test_bot_setup_opens_browser_when_real_urls_and_no_session` — previously untested positive case for browser login
- Added four `@pytest.mark.unit` tests for the leaderboard 1.5x cap: trim, no-trim at cap, log message, and `int()` floor vs `round()`
- Removed duplicate `test_bot_go_live_no_skips_summary_on_off_day` (identical to `test_bot_off_day_skips_summary_post`)
- Renamed `test_bot_already_live_still_posts_summary` → `test_bot_go_live_returns_games_from_espn` to accurately describe what is being tested
- Strengthened `test_bot_already_live_skips_go_live_prompt` — now asserts `post_message.call_count == 0` in addition to non-None return
- `get_input_safe` mock in `_standard_patches` has no silent default — tests that forget to set `side_effect` now fail loudly
- Leaderboard cap tests marked `@pytest.mark.unit`; `integration` and `unit` markers registered in `pytest.ini`

---

## [v1.1.0] — March 2026

### Added
- **Slack DM setup flow** — full interactive configuration via Slack DMs; no command line required
- **Bracket URL prompting via DM** — bot asks for men's and women's pool URLs over DM with `stop` / `no` / retry support
- **Browser login with DM feedback** — login failures sent as DMs with retry or manual entry fallback
- **Incomplete setup reminders** — if setup is paused mid-flow, bot reminds you the next weekday morning at 9am
- **`_clean_url` helper** — bracket URLs pasted from Slack (e.g. `<https://...|label>`) are stripped to plain URLs before saving
- **Legacy module documentation tests** — `bot_setup/slack_setup.py` identified as dead prototype; known issues documented in test suite

### Fixed
- **`MANUAL_TOP` stored as `null`** — empty bracket URLs no longer write `null` to config, preventing downstream iteration errors
- **`PLAYWRIGHT_STATE` ignored from config** — leaderboard fetching now uses `config["PLAYWRIGHT_STATE"]` with fallback to the module constant instead of always using the hardcoded value
- **`run_slack_dm_setup` mixed return type** — empty POOLS now returns `None` consistently; was incorrectly returning a 6-tuple, causing silent fall-through in the caller
- **Browser retry loop unbounded** — login retries now capped at `_MAX_BROWSER_RETRIES` in all code paths

### Tests
- Expanded from initial baseline to **312 tests**
- Added `_was_called_with_text` helper for cleaner `post_message` call assertions
- Added `MANUAL_TOP`, `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_STATE` to `_base_config()` to prevent latent flakiness from unexpected prompt consumption

---

## [v1.0.0] — March 2026

### Added
- Live game updates — posts to Slack the moment a game goes final
- Daily morning summaries — recap of yesterday's games with current standings
- Leaderboard tracking — scrapes CBS, ESPN, or Yahoo bracket pools for top N players
- Upset detection — flags upsets with ⚡🔥 in game messages
- Weekend posting control — optionally skip Saturdays and Sundays
- CLI setup flow — guided command-line configuration saved to `config.json`
- MIT License
- `config.example.json` — safe template with placeholder values
- `.gitignore` — excludes `config.json`, `venv`, session files, and temp files
- Full test suite