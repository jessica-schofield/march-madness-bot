import warnings
import pytest
from unittest.mock import patch, MagicMock


def pytest_configure(config):
    warnings.filterwarnings("ignore", category=Warning, module="urllib3")


# ---------------------------------------------------------------------------
# autouse — prevent ask_slack_credentials_cli from ever hitting real stdin
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _auto_patch_ask_slack_credentials_cli():
    """
    Automatically patch ask_slack_credentials_cli for every test.
    Returns config unchanged so tests that don't care about credentials
    are unaffected. Tests that need specific credential behaviour can
    override by patching bot_setup.bot_setup.ask_slack_credentials_cli
    themselves — their patch takes precedence over this autouse one.
    """
    with patch(
        "bot_setup.bot_setup.ask_slack_credentials_cli",
        side_effect=lambda c: {**c, "SLACK_WEBHOOK_URL": c.get("SLACK_WEBHOOK_URL") or "https://hooks.slack.com/services/TEST/TEST/TEST"}
    ):
        yield


# ---------------------------------------------------------------------------
# Shared config fixture used by test_integration.py and test_live_counter.py
# ---------------------------------------------------------------------------

@pytest.fixture
def base_config():
    def _make(**overrides):
        config = {
            "METHOD": "cli",
            "TOP_N": 3,
            "MINUTES_BETWEEN_MESSAGES": 30,
            "PLAYWRIGHT_HEADLESS": True,
            "PLAYWRIGHT_STATE": "playwright_state.json",
            "POOLS": [{"SOURCE": "cbs",
                       "MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/realpool1/standings",
                       "WOMEN_URL": "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/realpool2/standings"}],
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST/TEST/TEST",
            "SLACK_MANAGER_ID": "U012TEST",
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
        with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", go_live]) as m1, \
                patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: c) as m2, \
                patch("bot_setup.bot_setup.ensure_cbs_login") as m3, \
                patch("bot_setup.bot_setup.get_top_n_async") as m4, \
                patch("bot_setup.bot_setup.run_async", return_value=run_async_return) as m5, \
                patch("bot_setup.bot_setup.get_final_games", return_value=games_return) as m6, \
                patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c) as m7, \
                patch("bot_setup.bot_setup.load_flag", return_value=load_flag_return) as m8, \
                patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x) as m9, \
                patch("bot_setup.bot_setup.build_daily_summary", return_value=summary_return) as m10, \
                patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro") as m11, \
                patch("bot_setup.bot_setup.post_message") as m12, \
                patch("bot_setup.config.save_json") as m13:
            mocks.update({
                "get_input_safe": m1,
                "ask_slack_credentials_cli": m2,
                "ensure_cbs_login": m3,
                "get_top_n_async": m4,
                "run_async": m5,
                "get_final_games": m6,
                "ask_if_missing": m7,
                "load_flag": m8,
                "deduplicate_top_users": m9,
                "build_daily_summary": m10,
                "build_yearly_intro_message": m11,
                "post_message": m12,
                "save_json": m13,
            })
            yield mocks

    return _apply