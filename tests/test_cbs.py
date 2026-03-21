import asyncio
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cbs import (
    _build_top_n,
    _extract_espn,
    _format_user,
    get_espn_top_n,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_page(evaluate_results):
    """
    Build a minimal mock Playwright page for _extract_espn.
    evaluate_results: list of return values consumed in order per
    await page.evaluate() call.

    Call order inside _extract_espn:
      1-3: window.scrollBy (return value ignored)
      4:   main JS extraction → returns list[dict] or None
      5:   fallback headings dump (only reached when call 4 returns None)
    """
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(side_effect=evaluate_results)
    return page


# ---------------------------------------------------------------------------
# get_espn_top_n — no-cookies guard
# ---------------------------------------------------------------------------

def test_get_espn_top_n_no_cookies_returns_empty():
    """No cookies → should return empty list gracefully."""
    results = get_espn_top_n(
        "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group"
        "?id=b1e6fb01-f1eb-450b-8b77-0b994d62563e",
        n=5,
        playwright_state="nonexistent_state.json",
    )
    assert isinstance(results, list)
    assert results == []


# ---------------------------------------------------------------------------
# _format_user
# ---------------------------------------------------------------------------

def test_format_user_with_points():
    assert _format_user(1, "Alice", 120) == "Alice (120 pts)"


def test_format_user_single_point():
    assert _format_user(1, "Alice", 1) == "Alice (1 pt)"


def test_format_user_no_points_first():
    assert _format_user(1, "Alice", 0) == "Alice (1st place)"


def test_format_user_no_points_second():
    assert _format_user(2, "Bob", 0) == "Bob (2nd place)"


def test_format_user_no_points_third():
    assert _format_user(3, "Carol", 0) == "Carol (3rd place)"


def test_format_user_no_points_fourth():
    assert _format_user(4, "Dave", 0) == "Dave (4th place)"


def test_format_user_no_points_eleventh():
    assert _format_user(11, "Eve", 0) == "Eve (11th place)"


# ---------------------------------------------------------------------------
# _build_top_n
# ---------------------------------------------------------------------------

def test_build_top_n_empty():
    assert _build_top_n([], 5) == []


def test_build_top_n_basic():
    users = [(1, "Alice", 100), (2, "Bob", 90), (3, "Carol", 80)]
    assert _build_top_n(users, 2) == ["Alice (100 pts)", "Bob (90 pts)"]


def test_build_top_n_respects_ties():
    # Ranks 1, 1, 3 — asking for top 2 should include both rank-1 entries
    users = [(1, "Alice", 100), (1, "Bob", 100), (3, "Carol", 80)]
    result = _build_top_n(users, 2)
    assert len(result) == 2
    assert "Alice (100 pts)" in result
    assert "Bob (100 pts)" in result


def test_build_top_n_n_larger_than_list():
    assert _build_top_n([(1, "Alice", 100)], 10) == ["Alice (100 pts)"]


def test_build_top_n_sorts_by_rank():
    users = [(3, "Carol", 80), (1, "Alice", 100), (2, "Bob", 90)]
    result = _build_top_n(users, 3)
    assert result == ["Alice (100 pts)", "Bob (90 pts)", "Carol (80 pts)"]


def test_build_top_n_zero_points_uses_rank_suffix():
    users = [(1, "Alice", 0), (2, "Bob", 0)]
    assert _build_top_n(users, 2) == ["Alice (1st place)", "Bob (2nd place)"]


# ---------------------------------------------------------------------------
# _extract_espn — mocked Playwright page
# ---------------------------------------------------------------------------

def test_extract_espn_returns_entries():
    """Normal case: GROUP BRACKETS heading found, entries returned."""
    entries = [
        {"rank": 1, "name": "Alice", "points": 0},
        {"rank": 2, "name": "Bob", "points": 0},
        {"rank": 3, "name": "Carol", "points": 0},
    ]
    page = _make_page([None, None, None, entries])

    result = asyncio.run(_extract_espn(page, 5))

    assert result == [(1, "Alice", 0), (2, "Bob", 0), (3, "Carol", 0)]


def test_extract_espn_returns_none_when_heading_missing():
    """If GROUP BRACKETS heading not found, evaluate returns None → debug path → return None."""
    fallback_headings = ["MY BRACKETS", "RANK", "CHAMP"]
    page = _make_page([None, None, None, None, fallback_headings])

    result = asyncio.run(_extract_espn(page, 5))

    assert result is None


def test_extract_espn_empty_entries_list():
    """Heading found but no entries extracted → return empty list, not None."""
    page = _make_page([None, None, None, []])

    result = asyncio.run(_extract_espn(page, 5))

    assert result == []


def test_extract_espn_returns_tuples():
    """Each returned entry is a (rank, name, points) tuple."""
    entries = [{"rank": 1, "name": "Alice", "points": 0}]
    page = _make_page([None, None, None, entries])

    result = asyncio.run(_extract_espn(page, 5))

    assert isinstance(result, list)
    assert result[0] == (1, "Alice", 0)


def test_extract_espn_preserves_js_order():
    """Entries come back in the same order the JS returned them (sorting is caller's job)."""
    entries = [
        {"rank": 3, "name": "Carol", "points": 0},
        {"rank": 1, "name": "Alice", "points": 0},
        {"rank": 2, "name": "Bob", "points": 0},
    ]
    page = _make_page([None, None, None, entries])

    result = asyncio.run(_extract_espn(page, 5))

    assert [r[0] for r in result] == [3, 1, 2]


def test_extract_espn_calls_wait_for_timeout_correct_times():
    """Page waits are called the expected number of times.

    1 initial wait + 3 scroll iterations × 1 wait each + 1 final wait = 5
    """
    entries = [{"rank": 1, "name": "Alice", "points": 0}]
    page = _make_page([None, None, None, entries])

    asyncio.run(_extract_espn(page, 5))

    assert page.wait_for_timeout.await_count == 5


def test_extract_espn_fallback_evaluate_called_on_none():
    """When main extraction returns None, a second evaluate() call is made for debug."""
    fallback = ["RANK", "GROUP BRACKETS", "MY BRACKETS"]
    page = _make_page([None, None, None, None, fallback])

    result = asyncio.run(_extract_espn(page, 5))

    assert result is None
    # 3 scrollBy + 1 main extraction + 1 fallback headings dump = 5
    assert page.evaluate.await_count == 5


def test_extract_espn_points_always_zero():
    """ESPN group view never surfaces raw points — all entries have points=0."""
    entries = [
        {"rank": 1, "name": "Alice", "points": 0},
        {"rank": 2, "name": "Bob", "points": 0},
    ]
    page = _make_page([None, None, None, entries])

    result = asyncio.run(_extract_espn(page, 5))

    assert all(pts == 0 for _, _, pts in result)


def test_extract_espn_single_entry():
    """Works correctly with exactly one entry."""
    page = _make_page([None, None, None, [{"rank": 1, "name": "OnlyPerson", "points": 0}]])

    result = asyncio.run(_extract_espn(page, 5))

    assert result == [(1, "OnlyPerson", 0)]


def test_extract_espn_large_entry_list():
    """Handles a full-size leaderboard (200 entries) without issue."""
    entries = [{"rank": i + 1, "name": f"User{i+1}", "points": 0} for i in range(200)]
    page = _make_page([None, None, None, entries])

    result = asyncio.run(_extract_espn(page, 5))

    assert len(result) == 200
    assert result[0] == (1, "User1", 0)
    assert result[-1] == (200, "User200", 0)
