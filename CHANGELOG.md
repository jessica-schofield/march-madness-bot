# Changelog

## v1.0.0 — March 20, 2026

First public release! 🏀🎉

### Features
- Fetches live bracket standings from **ESPN**, **CBS Sports**, and **Yahoo** pools
- Posts daily Slack summaries with top players, leaderboard movers, and upset alerts
- Supports both **men's and women's** tournament pools simultaneously
- ESPN standings fetched via the gambit JSON API (no browser scraping needed after login)
- CBS and Yahoo standings fetched via headless Playwright browser
- Detects and deduplicates multi-group ESPN setups with interactive group picker
- Mock mode — prints messages to terminal instead of posting to Slack (great for testing)
- Weekend posting toggle
- Remembers previously posted games to avoid duplicates
- Interactive setup wizard — no config file editing required

### Technical
- 255 passing tests across 12 test files
- Full `pytest` suite with mocked Slack, ESPN API, and Playwright
- `config.example.json` included for easy onboarding
- MIT licensed