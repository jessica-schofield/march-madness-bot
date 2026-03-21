# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Hardcoded absolute paths in `status/yearly_setup_reminder.py` lines 111–113 replaced with `Path(__file__).parent.parent`-relative paths — bot no longer breaks when run outside `/Users/jess/march-madness-bot`

## [1.1.4] - 2026-03-21

### Changed
- Fixes config file and slack setup

## [2.0.0] - 2026-03-21

### Changed
- breaking change

## [1.1.0] - 2026-03-21

### Changed
- new feature

## [1.0.2] - 2026-03-21

### Changed
- what changed

## [1.0.1] - 2026-03-21

### Changed
- Fix webhook guard firing before pools check, 442 tests passing

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