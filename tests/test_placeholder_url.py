"""
Tests for _is_placeholder_url — ensures real pool URLs are never blocked
and known placeholders are always caught.

These tests would have caught the v1.1.2 regression where testpool123/standings
URLs were incorrectly flagged as placeholders, causing StopIteration in mocked tests.
"""
import pytest
from bot_setup.bot_setup import _is_placeholder_url


# ---------------------------------------------------------------------------
# Real URLs — must never be flagged as placeholders
# ---------------------------------------------------------------------------

REAL_URLS = [
    # Actual pool URLs (picks.cbssports.com with real-looking pool IDs)
    "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/kbxw63b2ge3deojqg4ydq===/standings",
    "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/abc123xyz/standings",
    # Other real sources
    "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id=12345",
    "https://tournament.fantasysports.yahoo.com/t1/group/67890",
    "https://men.realleague.org/standings",
    "https://women.realleague.org/standings",
]

@pytest.mark.parametrize("url", REAL_URLS)
def test_real_urls_are_not_placeholder(url):
    assert _is_placeholder_url(url) is False, (
        f"Real URL incorrectly flagged as placeholder: {url!r}\n"
        "This will cause URL prompts to fire in tests, exhausting mock side_effect lists."
    )


# ---------------------------------------------------------------------------
# Placeholder URLs — must always be flagged
# ---------------------------------------------------------------------------

PLACEHOLDER_URLS = [
    # Empty / None
    "",
    None,
    # example.com domains
    "https://example.com/standings",
    "https://men.example.com",
    "https://women.example.com/bracket",
    # Old fake CBS paths (pre-picks.cbssports.com)
    "https://cbssports.com/brackets/men/group/123",
    "https://cbssports.com/brackets/women/group/456",
    "https://www.cbssports.com/brackets/men/group/123",
    "https://www.cbssports.com/brackets/women/group/456",
    # Test fixture slugs — these are recognised placeholders
    "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/unittestpool1/standings",
    "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/unittestpool2/standings",
    "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/yourpool/standings",
]

@pytest.mark.parametrize("url", PLACEHOLDER_URLS)
def test_placeholder_urls_are_detected(url):
    assert _is_placeholder_url(url) is True, (
        f"Placeholder URL not detected: {url!r}\n"
        "This will cause _fetch_leaderboard to attempt a live scrape with a fake URL."
    )


# ---------------------------------------------------------------------------
# Regression: picks.cbssports.com paths are NEVER placeholders
# (v1.1.2 bug — testpool123 paths were flagged, breaking 25 tests)
# ---------------------------------------------------------------------------

def test_picks_cbssports_never_placeholder_regardless_of_pool_id():
    """Any picks.cbssports.com URL with a real /pools/<id>/standings structure is real.
    Known placeholder slugs (unittestpool*, yourpool, examplepool) are excluded."""
    pool_ids = [
        "kbxw63b2ge3deojqg4ydq===",
        "abc123xyz",
        "abc",
        "123",
        "realpool",
        "fake_but_real_format",
    ]
    for pool_id in pool_ids:
        url = f"https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/{pool_id}/standings"
        assert _is_placeholder_url(url) is False, (
            f"picks.cbssports.com URL with pool_id={pool_id!r} incorrectly flagged as placeholder"
        )