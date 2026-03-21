"""
Contract tests for get_top_n_async — ensures the function signature and
return shape stay stable so callers like _fetch_leaderboard don't break silently.

These tests would have caught the v1.1.2 bug where _fetch_leaderboard passed
'state_path' but get_top_n_async expected 'playwright_state'.
"""
import inspect
import pytest
from sources.cbs import get_top_n_async


def test_get_top_n_async_accepts_playwright_state_kwarg():
    """get_top_n_async must accept 'playwright_state' as a keyword argument."""
    sig = inspect.signature(get_top_n_async)
    assert "playwright_state" in sig.parameters, (
        "get_top_n_async missing 'playwright_state' kwarg — "
        "_fetch_leaderboard passes playwright_state=... and will get TypeError"
    )


def test_get_top_n_async_does_not_accept_state_path_kwarg():
    """Ensure the old wrong kwarg name 'state_path' is not silently accepted."""
    sig = inspect.signature(get_top_n_async)
    assert "state_path" not in sig.parameters, (
        "get_top_n_async has a 'state_path' param — callers should use 'playwright_state' instead. "
        "Remove or alias 'state_path' and update all call sites."
    )


def test_get_top_n_async_accepts_n_kwarg():
    """get_top_n_async must accept 'n' to control result count."""
    sig = inspect.signature(get_top_n_async)
    assert "n" in sig.parameters


def test_get_top_n_async_accepts_url_as_first_positional():
    """First positional arg must be the URL."""
    sig = inspect.signature(get_top_n_async)
    params = list(sig.parameters.keys())
    assert params[0] == "url", (
        f"Expected first param to be 'url', got {params[0]!r}"
    )


def test_get_top_n_async_is_coroutine():
    """get_top_n_async must be an async function so run_async() works correctly."""
    import asyncio
    assert asyncio.iscoroutinefunction(get_top_n_async), (
        "get_top_n_async is not async — run_async() will fail to await it"
    )
    