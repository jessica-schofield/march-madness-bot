import warnings
import pytest
from unittest.mock import patch, MagicMock


def pytest_configure(config):
    warnings.filterwarnings("ignore", category=Warning, module="urllib3")


# ---------------------------------------------------------------------------
# Shared config fixture used by test_integration.py and test_live_counter.py
# ---------------------------------------------------------------------------

@pytest.fixture
def base_config():
    """
    Minimal valid config for integration tests.
    Covers all keys needed by both test_integration.py and test_live_counter.py.
    Use base_config() to get a plain dict, or override specific keys via
    the dict's .update() / unpacking in each test.
    """
    def _make(**overrides):
        config = {
            "METHOD": "cli",
            "TOP_N": 3,
            "MINUTES_BETWEEN_MESSAGES": 30,
            "PLAYWRIGHT_HEADLESS": True,
            "PLAYWRIGHT_STATE": "playwright_state.json",
            "POOLS": [{"SOURCE": "cbs", "MEN_URL": "https://example.com/men", "WOMEN_URL": "https://example.com/women"}],
            "SLACK_WEBHOOK_URL": "",
            "MOCK_SLACK": True,
            "POST_ON_WEEKENDS": True,
            "MANUAL_TOP": ["Alice (100)", "Bob (90)", "Carol (80)"],
        }
        config.update(overrides)
        return config
    return _make


@pytest.fixture
def standard_run_setup_patches():
    """
    Context manager that applies the full set of bot_setup patches used
    in almost every integration test. Yields a dict of the named mocks.

    Usage:
        def test_something(standard_run_setup_patches):
            with standard_run_setup_patches(go_live="n") as mocks:
                run_setup(config)
            mocks["post_message"].assert_not_called()
    """
    from contextlib import contextmanager

    @contextmanager
    def _apply(
        go_live="n",
        run_async_return=None,
        games_return=None,
        summary_return=None,
        load_flag_return=None,
    ):
        run_async_return = run_async_return if run_async_return is not None else []
        games_return = games_return if games_return is not None else []
        summary_return = summary_return if summary_return is not None else ([{"type": "section"}], False)
        load_flag_return = load_flag_return if load_flag_return is not None else {"LIVE_FOR_YEAR": False}

        mocks = {}
        with patch("bot_setup.get_input_safe", side_effect=["cli", go_live]) as m1, \
                patch("bot_setup.ensure_cbs_login") as m2, \
                patch("bot_setup.get_top_n_async") as m3, \
                patch("bot_setup.run_async", return_value=run_async_return) as m4, \
                patch("bot_setup.get_final_games", return_value=games_return) as m5, \
                patch("bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c) as m6, \
                patch("bot_setup.load_flag", return_value=load_flag_return) as m7, \
                patch("bot_setup.deduplicate_top_users", side_effect=lambda x: x) as m8, \
                patch("bot_setup.build_daily_summary", return_value=summary_return) as m9, \
                patch("bot_setup.build_yearly_intro_message", return_value="intro") as m10, \
                patch("bot_setup.post_message") as m11, \
                patch("config.save_json") as m12:
            mocks.update({
                "get_input_safe": m1,
                "ensure_cbs_login": m2,
                "get_top_n_async": m3,
                "run_async": m4,
                "get_final_games": m5,
                "ask_if_missing": m6,
                "load_flag": m7,
                "deduplicate_top_users": m8,
                "build_daily_summary": m9,
                "build_yearly_intro_message": m10,
                "post_message": m11,
                "save_json": m12,
            })
            yield mocks

    return _apply