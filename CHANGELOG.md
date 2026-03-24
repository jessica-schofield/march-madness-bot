# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-03-24

### Added
- `tests/test_events.py` — 12 tests for `slack_bot/events.py` (member join + DM reply handling)
- `tests/test_slack_dm.py` — 8 tests for `slack_bot/slack_dm.py` (DM client, send, pending DM flag)
- `tests/test_yearly_setup_reminder.py` — 17 tests for `status/yearly_setup_reminder.py`
- `tests/test_event_server.py` — 5 tests for `slack_bot/event_server.py` Flask routes
- `tests/test_yearly_setup_cron.py` — 5 tests for `status/yearly_setup_cron.py` cron entrypoint

### Changed
- `bot_setup/setup_cli.py`: moved `dotenv`/`os` imports to module level
- `bot_setup/bot_setup.py`: removed redundant inline `urllib.parse` and `json` imports
- `status/yearly_setup_reminder.py`: moved `save_json`, `check_championship_final`, and `post_message` to module-level imports
- `scripts/review_agent.py`: added allowlists for intentionally-accepted NAIVE_DATETIME, IMPORT_INSIDE_FUNCTION, and NO_TEST_FILE patterns — review agent now reports 0 findings on a clean codebase

### Fixed
- `tests/test_input_exhaustion.py` `TestInputMethodRouting` — added missing `send_dm_blocks` and `poll_for_reply` mocks; 6 previously-failing tests now pass
- `tests/test_espn.py` `TestAdvanceTournamentDates` — updated `save_json` patch targets after import move
- `tests/test_setup_credentials.py` — updated `set_key` patch target after import move



### Changed
- Various Bug Fixes

## [Unreleased]

## [2.0.3] - 2026-03-22

### Fixed
- `clear_pending_dm` now imported inside `run_slack_dm_setup` — was causing silent `NameError` at runtime
- Slack setup no longer returns early after collecting preferences — falls through to leaderboard fetch and go-live preview
- Removed stale `pending_dm.json` from repository

## [2.0.2] - 2026-03-22

### Fixed
- Double-send bug in Slack DM setup — `run_slack_dm_setup` was called twice due to missing `return` after first call completed
- `test_bot_token_saved_to_env_when_provided` now patches `dotenv.set_key` via `patch.object` to avoid real `.env` token leaking into test environment
- `test_slack_setup_legacy.py` permanently removed — referenced deleted `bot_setup.slack_setup` module

## [2.0.1] - 2026-03-21

### Fixed
- Hardcoded absolute paths in `status/yearly_setup_reminder.py` replaced with `Path(__file__).parent.parent`-relative constants
- `datetime.utcnow()` in `slack_bot/slack_dm.py` replaced with timezone-aware `datetime.now(timezone.utc)`
- `_ESPN_CHALLENGE_ID_FALLBACK` constant added at module level in `sources/cbs.py`
- Removed deleted `bot_setup/slack_setup.py` test files (`test_slack_setup.py`, `test_slack_setup_legacy.py`)

## [2.0.0] - 2026-03-21

### Changed
- Breaking change

## [1.1.4] - 2026-03-21

### Fixed
- Config file and slack setup

## [1.1.2] - 2026-03-21

### Added
- `_advance_tournament_dates` — automatically bumps `TOURNAMENT_END_MEN` and `TOURNAMENT_END_WOMEN` in `config.json` by one year when both championships are final
- `_update_yearly_crontab` — automatically rewrites the yearly crontab entry to March 10 next year after season wrap-up; no manual crontab edits needed year-over-year
- `test_placeholder_url.py` — parametrised tests ensuring real `picks.cbssports.com` URLs are never flagged as placeholders and all known fake URLs are always caught
- `test_cbs_scraper_contract.py` — contract tests locking in `get_top_n_async` signature (`url`, `n`, `playwright_state`) to prevent kwarg mismatch regressions

### Fixed
- CBS scraper now correctly targets `picks.cbssports.com` instead of `www.cbssports.com`; re-saved Playwright session scoped to `/standings` resolves redirect-to-`/join` bug
- `_fetch_leaderboard` now passes `playwright_state` as keyword arg to `get_top_n_async` (was incorrectly using `state_path`)
- `_is_placeholder_url` no longer flags real `picks.cbssports.com` pool URLs as placeholders; only blocks known fake paths and `example.com` domains
- Test fixture URLs updated to `picks.cbssports.com/…/unittestpool1/standings` format so they no longer trigger URL prompts and exhaust mock `side_effect` lists
- Duplicate `## Running` section removed from README
- README crontab instructions updated: only one cron entry ever needed; yearly scheduling is now fully automatic

### Changed
- `check_tournament_end` now calls `_advance_tournament_dates` and `_update_yearly_crontab` after wrap-up — season maintenance is fully self-contained
- `status/yearly_setup_cron.py` retained for manual fallback but no longer needs to be in crontab
- Test count: 411 → 434

## [1.1.1] - 2026-03-21

### Fixed
- Placeholder URL detection added via `_is_placeholder_url` to prevent setup from skipping URL prompts when config contains unfilled example values
- `_fetch_leaderboard` returns early on placeholder URLs instead of attempting a live scrape

## [1.1.0] - 2026-03-20

### Added
- Multi-pool support via `POOLS` config key
- `SOURCE` field per pool (`cbs`, `espn`, `yahoo`, `custom`)
- `deduplicate_top_users` to handle duplicate names across men's/women's leaderboards
- `_ping_live_counter` to report live bot count on go-live
- `LIVE_COUNTER_URL` config key
- Bounded browser login retry loop (`_MAX_BROWSER_RETRIES = 3`)
- `TOURNAMENT_DATES_HELP` reference in setup CLI

### Changed
- `run_setup` now returns a 6-tuple `(config, method, men_games, women_games, top_men, top_women)` in all code paths
- Browser login skipped when both pool URLs are placeholders

## [1.0.0] - 2026-03-01

### Added
- Initial release
- CBS Sports bracket scraper via Playwright
- ESPN game results via `get_final_games`
- Daily summary + yearly intro Slack messages
- CLI and Slack DM setup flows
- `playwright_state.json` session persistence
- `SEEN_FILE` deduplication for game update posts
- `YEARLY_FLAG_FILE` for go-live state tracking